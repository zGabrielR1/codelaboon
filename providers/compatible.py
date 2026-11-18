"""Live OpenAI-compatible catalogues, including a strictly free OpenRouter lane."""
import os
from urllib.parse import urlsplit

import requests

from providers.base import BaseProvider


class CompatibleProvider(BaseProvider):
    base_url = ""
    environment = ""
    transport = requests

    def credential(self):
        return self.api_key.strip() or os.environ.get(self.environment, "").strip()

    def validate_api_key(self):
        return self.keyless or bool(self.credential())

    def headers(self):
        return {"Authorization": f"Bearer {self.credential()}"} if self.credential() else {}

    def list_models(self):
        if not self.validate_api_key():
            return []
        try:
            with self.transport.get(self.base_url.rstrip("/") + "/models", headers=self.headers(), timeout=10, allow_redirects=False) as response:
                response.raise_for_status()
                rows = response.json()["data"]
                if not isinstance(rows,list):
                    raise ValueError("Invalid model catalog")
                models = list(dict.fromkeys(row["id"] for row in rows
                              if isinstance(row, dict) and isinstance(row.get("id"), str)
                              and self.accepts(row)))
                self.live_models = list(models)
                self.discovery_error = None
                return models
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            self.discovery_error = type(error).__name__
            return [model for model in self.models if self.accepts({"id": model})]

    def accepts(self, row):
        return True

    def chat(self, model, messages, **kwargs):
        if not self.validate_api_key() or not self.accepts({"id": model}):
            raise ValueError("Model or credential is unavailable")
        body = {"model": model, "messages": messages, "stream": False,
                "max_tokens": kwargs.get("max_tokens", 4096)}
        if getattr(self,"zero_price_cap",False):
            body["provider"]={"max_price":{"prompt":0,"completion":0}}
        with self.transport.post(self.base_url.rstrip("/") + "/chat/completions",
                           headers=self.headers(), json=body, timeout=kwargs.get("timeout", 180), allow_redirects=False) as response:
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


class LocalProvider(CompatibleProvider):
    """Ollama, llama.cpp or another explicitly configured loopback model server."""
    base_url = "http://127.0.0.1:11434/v1"
    keyless = True

    def __init__(self, api_key="", models=None, base_url=None):
        super().__init__(api_key, models, base_url)
        parsed = urlsplit(self.base_url)
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost")
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Local models require a loopback HTTP base URL")
        self.transport = requests.Session()
        self.transport.trust_env = False


class OpenRouterFreeProvider(CompatibleProvider):
    zero_price_cap = True
    base_url = "https://openrouter.ai/api/v1"
    environment = "OPENROUTER_API_KEY"

    def accepts(self, row):
        from decimal import Decimal, InvalidOperation
        model = row['id']
        named_free = model.endswith(':free') or model == 'openrouter/free'
        pricing = row.get('pricing')
        if pricing is None:
            return named_free or model in (getattr(self, 'live_models', None) or [])
        if not isinstance(pricing, dict):
            return False
        architecture = row.get('architecture') or {}
        outputs = architecture.get('output_modalities', []) if isinstance(architecture, dict) else []
        if outputs and 'text' not in outputs:
            return False
        if not named_free and 'text' not in outputs:
            return False
        try:
            return (
                all(Decimal(str(pricing.get(key, 'NaN'))) == 0 for key in ('prompt', 'completion'))
                and all(Decimal(str(price)) == 0 for price in pricing.values() if price is not None)
            )
        except (InvalidOperation, ValueError, TypeError):
            return False

    def free_models(self):
        return self.list_models()


class MistralLabsProvider(CompatibleProvider):
    """Mistral's documented zero-price Labs namespace."""
    base_url = "https://api.mistral.ai/v1"
    environment = "MISTRAL_API_KEY"

    def __init__(self, api_key="", models=None, base_url=None):
        if base_url and base_url.rstrip("/") != self.base_url:
            raise ValueError("Mistral Labs requires the official Mistral endpoint")
        super().__init__(api_key, models, self.base_url)

    def accepts(self, row):
        return row['id'].startswith("labs-")

    def free_models(self):
        return self.list_models()


class GroqProvider(CompatibleProvider):
    base_url = "https://api.groq.com/openai/v1"
    environment = "GROQ_API_KEY"


class CerebrasProvider(CompatibleProvider):
    base_url = "https://api.cerebras.ai/v1"
    environment = "CEREBRAS_API_KEY"


class ZaiFreeProvider(CompatibleProvider):
    """Only Z.AI's explicitly zero-priced Flash models, never paid FlashX/GLM5 IDs."""
    base_url = 'https://api.z.ai/api/paas/v4'
    environment = 'ZAI_API_KEY'
    FREE_IDS = {'glm-4.7-flash', 'glm-4.5-flash', 'glm-4.6v-flash'}

    def __init__(self, api_key='', models=None, base_url=None):
        super().__init__(api_key,models,base_url)
        self.default_models=sorted(self.FREE_IDS)
        self.priced_free=set()

    def refresh_prices(self):
        import time
        if getattr(self,'prices_until',0)>time.monotonic():
            return
        self.priced_free=set()
        try:
            response=requests.get('https://docs.z.ai/guides/overview/pricing.md',timeout=10,allow_redirects=False)
            response.raise_for_status()
            for line in response.text.splitlines():
                cells=[cell.strip().lower() for cell in line.lstrip('> ').split('|')[1:-1]]
                import re
                if len(cells)==5 and re.fullmatch(r'glm-[a-z0-9.-]+',cells[0]) and all(cell=='free' for cell in cells[1:]):
                    self.priced_free.add(cells[0])
            self.prices_until=time.monotonic()+3600
        except requests.RequestException:
            self.prices_until=time.monotonic()+60

    def accepts(self,row):
        self.refresh_prices()
        return row.get('id') in self.priced_free

    def list_models(self):
        if not self.validate_api_key():
            return []
        self.refresh_prices()
        if not self.priced_free:
            self.discovery_error='free_pricing_unverified'
            return []
        models=super().list_models()
        return models if self.live_models is not None else [model for model in self.models or sorted(self.priced_free) if self.accepts({'id':model})]


class HowToFixProvider(CompatibleProvider):
    """Account-scoped live catalogue; credits/prices are not a zero-cost promise."""
    base_url = 'https://api.howtofix.id/v1'
    environment = 'HOWTOFIX_API_KEY'
    signup_url = 'https://howtofix.id/'

    def credential(self):
        return super().credential() or os.environ.get('HTF_API_KEY','').strip()


class VercelProvider(CompatibleProvider):
    """Vercel AI Gateway API keys and provider/model IDs; an explicit credit lane."""
    base_url = 'https://ai-gateway.vercel.sh/v1'
    environment = 'AI_GATEWAY_API_KEY'
    signup_url = 'https://vercel.com/ai-gateway'

    def __init__(self,api_key='',models=None,base_url=None):
        super().__init__(api_key,models,base_url)
        parsed=urlsplit(self.base_url)
        if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path.rstrip('/') not in ('','/v1')):
            raise ValueError('Vercel AI Gateway requires an HTTPS root URL or /v1 base URL')
        self.base_url=self.base_url.rstrip('/')
        if not self.base_url.endswith('/v1'):self.base_url+='/v1'


class VercelFreeProvider(VercelProvider):
    """Only live, uniformly zero-priced text models; never credit-funded models."""
    def __init__(self,api_key='',models=None,base_url=None):
        super().__init__(api_key,models,base_url)
        self.priced_free=set()
        self.prices_until=0
        self.price_scope=None

    @staticmethod
    def zero_priced(row):
        from decimal import Decimal,InvalidOperation
        if not isinstance(row,dict) or row.get('type')!='language' or not isinstance(row.get('id'),str):return False
        prices=row.get('pricing')
        if not isinstance(prices,dict) or not {'input','output'}<=prices.keys():return False
        if prices.get('varies_by_provider',False) is not False:return False
        try:
            return all(not isinstance(value,bool) and Decimal(str(value)).is_finite() and Decimal(str(value))==0
                       for key,value in prices.items() if key!='varies_by_provider')
        except (InvalidOperation,ValueError,TypeError):return False

    def refresh_prices(self,force=False):
        import hashlib,time
        scope=hashlib.sha256((self.base_url+'\0'+self.credential()).encode()).hexdigest()
        if not force and self.price_scope==scope and time.monotonic()<self.prices_until:return
        self.priced_free=set();self.live_models=[];self.price_scope=scope
        self.prices_until=time.monotonic()+15
        if not self.validate_api_key():return
        try:
            with self.transport.get(self.base_url+'/models',headers=self.headers(),timeout=10,allow_redirects=False) as response:
                response.raise_for_status();rows=response.json()['data']
                if not isinstance(rows,list):raise ValueError('Invalid model catalog')
                models=list(dict.fromkeys(row['id'] for row in rows if self.zero_priced(row)))
            self.priced_free=set(models);self.live_models=models;self.discovery_error=None
            self.prices_until=time.monotonic()+60
        except (requests.RequestException,ValueError,KeyError,TypeError) as error:
            self.discovery_error=type(error).__name__

    def accepts(self,row):
        self.refresh_prices()
        return row.get('id') in self.priced_free

    def list_models(self):
        self.refresh_prices(force=True)
        return list(self.live_models)

    def free_models(self):return self.list_models()


class CopilotProvider(CompatibleProvider):
    """GitHub Copilot account models using the pinned OpenCode OAuth protocol."""
    base_url = 'https://api.githubcopilot.com'
    signup_url = 'https://github.com/settings/copilot'
    environment = 'COPILOT_GITHUB_TOKEN'

    def __init__(self,api_key='',models=None,base_url=None):
        super().__init__(api_key,models,base_url)
        if self.base_url.rstrip('/')!=type(self).base_url:
            raise ValueError('Copilot account tokens require the official Copilot API endpoint')

    def credential(self):
        from codelaboon.copilot_auth import credential
        return self.api_key.strip() or credential()

    def headers(self,messages=()):
        return {**super().headers(),'User-Agent':'codelaboon','Openai-Intent':'conversation-edits',
                'x-initiator':'agent' if messages and messages[-1].get('role')!='user' else 'user'}

    def accepts(self,row):
        endpoints=row.get('supported_endpoints')
        policy=row.get('policy',{})
        return (not endpoints or '/chat/completions' in endpoints) and (not isinstance(policy,dict) or policy.get('state','enabled')=='enabled')

    def chat(self,model,messages,**kwargs):
        if not self.validate_api_key():raise ValueError('Run codelaboon login copilot first')
        response=self.transport.post(self.base_url+'/chat/completions',headers=self.headers(messages),
            json={'model':model,'messages':messages,'stream':False,'max_tokens':kwargs.get('max_tokens',4096)},timeout=kwargs.get('timeout',180),allow_redirects=False)
        try:
            response.raise_for_status();return response.json()['choices'][0]['message']['content']
        finally:response.close()

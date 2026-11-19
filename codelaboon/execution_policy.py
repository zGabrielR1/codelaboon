"""Explicit per-task engine permissions; never grants operating-system elevation."""
import os


def full_access():
    mode=os.environ.get('CODELABOON_WORK_PERMISSIONS','default')
    if mode not in ('default','full'):raise ValueError('Worker permissions must be default or full')
    return mode=='full'


def profile(selected='coding'):
    value=os.environ.get('CODELABOON_WORK_PROFILE',selected)
    if value not in ('coding','security'):raise ValueError('Worker profile must be coding or security')
    return value


def child_environment(task):
    permissions=task.get('permissions','default');selected=task.get('profile','coding')
    if permissions not in ('default','full') or selected not in ('coding','security'):raise ValueError('Invalid task execution policy')
    environment=dict(os.environ)
    environment.pop('CODELABOON_TASK_CHAT_MODEL',None)
    for name in ('CODELABOON_DESKTOP_MCP', 'CODELABOON_FOREGROUND_TASK', 'CODELABOON_NATIVE_DESKTOP',
                 'CODELABOON_DESKTOP_VISION_MODEL', 'CODELABOON_DESKTOP_TASK_ID'):
        environment.pop(name, None)
    return dict(environment,CODELABOON_WORK_PERMISSIONS=permissions,CODELABOON_WORK_PROFILE=selected,
                CODELABOON_ROUTING_TASK='security' if selected=='security' else 'coding',
                CODELABOON_WORK_TRACE='1' if task.get('supervision',{}).get('enabled') else '0')

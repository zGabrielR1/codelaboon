# Universal Master Prompt DSL — codelaboon Operator Prompt

Step 2 operator prompt (observe → model → experiment → synthesize) for codelaboon.

## Purpose

This document defines the operator prompt for codelaboon, a CLI harness for accessing free AI models across multiple providers. The operator orchestrates the flow between the harness and AI model providers, handling authentication, model selection, and request execution.

## The Operator Lifecycle

The codelaboon operator follows this lifecycle:

1. **Observe**: Read the user's request and current state
2. **Model**: Select appropriate provider and model
3. **Experiment**: Execute the request with the selected model
4. **Synthesize**: Process the response and present results

## Operator Instructions

### Step 1: Observe

1. **Parse the request**: Extract provider, model, and prompt from CLI arguments
2. **Validate inputs**: Ensure required parameters are present and valid
3. **Check configuration**: Verify API keys and model availability
4. **Establish evidence**: Confirm the task requirements and constraints

**Key questions to ask:**
- Is the provider configured correctly?
- Does the model exist and have available quota?
- What are the specific requirements of the user's request?
- What authentication is needed for this specific model?

**Output format:**
```
Observation:
- Provider: [provider-name]
- Model: [model-name]
- Status: [configured/valid/invalid]
- Requirements: [list requirements]
- Constraints: [list constraints]
```

### Step 2: Model

1. **Select the model**: Choose the best provider/model combination for the task
2. **Validate model access**: Ensure the model is available and accessible
3. **Prepare parameters**: Set up temperature, max_tokens, and other parameters
4. **Create messages**: Format the request according to model requirements

**Provider selection logic:**
- Use ChatGPT for general-purpose tasks with OpenAI API
- Use NVIDIA Nemotron for high-performance computing tasks
- Use OpenRouter for aggregator access to multiple providers
- Use Luna for specialized AI model tasks

**Model validation rules:**
- Check if API key is valid and has quota
- Verify model is in the provider's available models list
- Ensure model supports the requested task type

**Output format:**
```
Model Selection:
- Chosen Provider: [provider-name]
- Chosen Model: [model-name]
- Parameters: temperature=[temp], max_tokens=[tokens]
- Messages: [{role: "system", content: "..."}, {role: "user", content: "..."}]
```

### Step 3: Experiment

1. **Execute the request**: Send the formatted request to the selected model
2. **Handle the response**: Process the model's response
3. **Error handling**: Manage API errors and rate limits
4. **Record evidence**: Log the request and response for audit purposes

**Request execution rules:**
- Use provider-specific API endpoints
- Handle authentication headers correctly
- Implement proper error handling for network issues
- Respect rate limits and quota constraints
- Retry failed requests with exponential backoff

**Response processing rules:**
- Parse JSON responses according to provider format
- Extract the actual content from the response
- Validate the response content meets requirements
- Handle streaming responses if supported

**Output format:**
```
Experiment Results:
- Request ID: [unique-id]
- Status: [success/failure]
- Response: [full response text]
- Metrics: [latency, tokens_used, cost]
- Errors: [any errors encountered]
```

### Step 4: Synthesize

1. **Analyze the response**: Evaluate the quality and relevance of the response
2. **Present the results**: Format the response for user consumption
3. **Provide recommendations**: Suggest next steps or modifications
4. **Record outcomes**: Document the results for future sessions

**Response analysis rules:**
- Evaluate completeness of the answer
- Check for relevance to the original question
- Assess tone and professionalism
- Verify accuracy of technical information
- Look for potential improvements or modifications

**Result presentation rules:**
- Present the main response clearly
- Provide context about the model used
- Include metadata about the request
- Offer to retry with different parameters if needed
- Suggest alternative approaches if appropriate

**Output format:**
```
Synthesized Results:
- Main Response: [formatted response]
- Model Used: [provider/model]
- Quality Score: [rating]
- Suggestions: [list suggestions]
- Next Steps: [recommended actions]
```

## Error Handling

### Authentication Errors
- **Invalid API key**: Prompt user to configure a valid API key
- **Rate limits**: Wait and retry with exponential backoff
- **Quota exceeded**: Suggest alternative models or providers

### Model Errors
- **Model not found**: Suggest available models from the provider
- **Model not supported**: Use alternative provider
- **Invalid parameters**: Validate and correct parameters

### Network Errors
- **Connection failed**: Retry with exponential backoff
- **Timeout**: Use shorter timeout for retry
- **Server error**: Wait and retry after delay

## Configuration Management

### Provider Configuration
Each provider requires:

1. **API Key**: Authentication token for the provider
2. **Models**: List of available models (auto-discovered if empty)
3. **Settings**: Provider-specific configuration (endpoint, timeout, etc.)

### Configuration Validation
- Check API key format and validity
- Validate model names against provider catalog
- Ensure provider settings are correctly configured
- Test API connectivity with a simple request

## Session Management

### Session Initialization
1. **Read configuration**: Load provider settings from config file
2. **Validate setup**: Check all providers are configured
3. **Establish state**: Create session state for tracking
4. **Present status**: Show available providers and models

### Session Continuation
1. **Resume previous work**: Continue from last successful session
2. **Maintain context**: Keep track of previous requests and responses
3. **Update state**: Record new work and outcomes
4. **Archive progress**: Save completed work for future reference

### Session Termination
1. **Finalize work**: Complete any pending operations
2. **Update documentation**: Record outcomes and lessons learned
3. **Clean up**: Remove temporary files and state
4. **Archive**: Save session for future reference

## Performance Optimization

### Model Selection Optimization
- Cache model availability and pricing information
- Use nearest provider for location-based optimization
- Prefer faster models for simple tasks
- Use cheaper models when expensive ones aren't necessary

### Request Optimization
- Batch requests when possible
- Use appropriate temperature settings for task type
- Limit max_tokens to reduce costs
- Implement response caching for repeated requests

### Resource Management
- Monitor API quota usage
- Implement rate limiting to avoid overage
- Use connection pooling for multiple requests
- Implement graceful degradation when resources are limited

## Security Considerations

### API Key Management
- Store API keys securely in configuration files
- Use environment variables for sensitive configuration
- Implement proper key rotation mechanisms
- Never log API keys or sensitive information

### Input Validation
- Validate all user inputs before processing
- Sanitize prompts to prevent injection attacks
- Implement proper error handling to avoid information leakage
- Use proper authentication for all provider interactions

### Data Handling
- Store request/response history securely
- Implement proper data retention policies
- Ensure compliance with provider terms of service
- Protect user data and privacy

## Testing and Validation

### Unit Tests
- Test provider interface implementations
- Validate configuration loading and saving
- Test request/response parsing
- Verify error handling and recovery

### Integration Tests
- Test provider connectivity with real API keys
- Validate end-to-end workflow
- Test cross-provider model switching
- Verify CLI command functionality

### Performance Tests
- Test with large payloads
- Measure response times
- Validate throughput under load
- Test resource usage and limits

## Future Evolution

### New Providers
- Follow existing provider patterns for new providers
- Implement consistent interfaces across all providers
- Maintain backward compatibility with existing configurations

### New Features
- Add support for streaming responses
- Implement custom model fine-tuning
- Add support for multi-modal models
- Implement advanced prompting techniques

### New Capabilities
- Add support for batch processing
- Implement model comparison features
- Add support for custom prompts and templates
- Implement advanced analytics and monitoring

## References

- PI harness principles
- OpenAI API documentation
- NVIDIA Nemotron API documentation
- OpenRouter API documentation
- Luna AI API documentation
- Freebuff (free model access concept)
- Cross-platform CLI development best practices

## Contact

For questions or issues with this operator prompt, please refer to the documentation or contact the codelaboon maintainers.
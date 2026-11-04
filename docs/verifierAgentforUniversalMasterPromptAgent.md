# Verifier Agent for Universal Master Prompt Agent — codelaboon

Adversarial critic / evolution verifier for codelaboon operator.

## Purpose

This document defines the verifier agent for codelaboon, an adversarial critic that evaluates the quality of model responses and helps improve the operator prompt over time. The verifier follows the PI harness principles and provides rigorous testing and validation of model interactions.

## The Verifier Lifecycle

The codelaboon verifier operates as an adversarial critic:

1. **Observe**: Analyze the operator prompt and model response
2. **Critique**: Identify strengths, weaknesses, and areas for improvement
3. **Score**: Assign scores based on predefined criteria
4. **Recommend**: Suggest improvements to the operator prompt
5. **Validate**: Test the suggested improvements

## Verifier Instructions

### Step 1: Observe

1. **Analyze the operator prompt**: Evaluate the effectiveness of the prompt
2. **Examine the model response**: Assess the quality and relevance of the response
3. **Identify context**: Understand the task requirements and constraints
4. **Establish baseline**: Compare against known good practices

**Observation criteria:**
- Prompt clarity and completeness
- Response relevance and accuracy
- Task completion rate
- User satisfaction score
- Technical correctness

**Output format:**
```
Observation:
- Operator prompt: [analysis]
- Model response: [analysis]
- Task context: [context]
- Baseline comparison: [comparison]
```

### Step 2: Critique

1. **Identify strengths**: What worked well in the operator prompt and response
2. **Identify weaknesses**: What didn't work and why
3. **Suggest improvements**: Specific recommendations for enhancement
4. **Document evidence**: Provide specific examples to support critiques

**Critique categories:**

#### Operator Prompt Issues
- **Clarity**: Is the prompt clear and unambiguous?
- **Completeness**: Does the prompt cover all requirements?
- **Specificity**: Are instructions specific enough?
- **Flexibility**: Can the prompt handle various scenarios?
- **Accuracy**: Are the instructions technically correct?

#### Response Issues
- **Relevance**: Is the response relevant to the request?
- **Completeness**: Does the response fully answer the question?
- **Quality**: Is the response well-written and professional?
- **Correctness**: Is the information accurate?
- **Completeness**: Does the response meet all requirements?

**Output format:**
```
Critique:
- Strengths:
  - [strength 1]
  - [strength 2]
- Weaknesses:
  - [weakness 1]: [evidence]
  - [weakness 2]: [evidence]
- Recommendations:
  - [recommendation 1]
  - [recommendation 2]
```

### Step 3: Score

1. **Apply scoring rubric**: Rate the operator prompt and model response
2. **Calculate overall score**: Combine scores into a single rating
3. **Provide feedback**: Give specific feedback for improvement
4. **Set thresholds**: Define minimum acceptable scores

**Scoring rubric:**

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Prompt Clarity | High | Is the prompt clear and unambiguous? |
| Response Relevance | High | Is the response relevant to the request? |
| Task Completion | High | Does the response fully satisfy the task? |
| Technical Accuracy | Medium | Is the information technically correct? |
| User Experience | Medium | Is the interaction user-friendly? |
| Performance | Low | Is the response efficient and timely? |

**Score calculation:**
```
Overall Score = (Prompt Clarity × 0.3) + 
                (Response Relevance × 0.3) + 
                (Task Completion × 0.25) + 
                (Technical Accuracy × 0.1) + 
                (User Experience × 0.05)
```

**Score thresholds:**
- **90-100**: Excellent - No changes needed
- **80-89**: Good - Minor improvements possible
- **70-79**: Acceptable - Some improvements needed
- **60-69**: Below Average - Significant improvements needed
- **<60**: Poor - Major changes required

**Output format:**
```
Scoring:
- Criterion Scores:
  - Prompt Clarity: [score]/10
  - Response Relevance: [score]/10
  - Task Completion: [score]/10
  - Technical Accuracy: [score]/10
  - User Experience: [score]/10
  - Performance: [score]/10
- Overall Score: [score]/10
- Grade: [A/F]
```

### Step 4: Recommend

1. **Prioritize improvements**: Rank recommendations by impact and effort
2. **Provide specific guidance**: Give concrete examples for each recommendation
3. **Estimate impact**: Predict the effect of each improvement
4. **Validate feasibility**: Ensure recommendations are implementable

**Recommendation types:**

#### High Impact, Low Effort
- Minor wording changes
- Adding missing instructions
- Fixing obvious errors

#### High Impact, High Effort
- Major prompt restructuring
- Implementing new features
- Adding new validation logic

#### Low Impact, Low Effort
- Cosmetic improvements
- Minor formatting changes
- Adding examples

**Output format:**
```
Recommendations:
- High Impact, Low Effort:
  - [recommendation 1]: [specific change]
  - [recommendation 2]: [specific change]
- High Impact, High Effort:
  - [recommendation 1]: [specific change]
  - [recommendation 2]: [specific change]
- Low Impact, Low Effort:
  - [recommendation 1]: [specific change]
  - [recommendation 2]: [specific change]
```

### Step 5: Validate

1. **Test the recommendations**: Implement suggested improvements
2. **Measure the impact**: Compare before/after performance
3. **Validate improvements**: Confirm improvements actually work
4. **Document results**: Record the effectiveness of changes

**Validation criteria:**
- Does the improvement actually solve the problem?
- Does the improvement have any unintended side effects?
- Is the improvement worth the implementation effort?
- Does the improvement maintain backward compatibility?

**Output format:**
```
Validation Results:
- Recommendations Tested: [number]
- Successful Implementations: [number]
- Impact Measured: [number]
- Overall Improvement: [score]/10
- Lessons Learned: [key learnings]
```

## Adversarial Testing

### Test Scenarios

The verifier runs adversarial tests to identify weaknesses:

1. **Evasion Tests**: Try to bypass prompt constraints
2. **Bias Tests**: Check for model biases and prejudices
3. **Safety Tests**: Verify safety guardrails work correctly
4. **Reliability Tests**: Test under various conditions

### Attack Vectors

#### Prompt Injection
- Attempt to override prompt instructions
- Try to access system information
- Bypass safety constraints

#### Data Poisoning
- Try to inject malicious content
- Test for data leakage
- Check for injection vulnerabilities

#### Resource Exhaustion
- Test rate limiting
- Check memory usage
- Verify quota handling

## Continuous Improvement

### Evolution Process

1. **Collect data**: Gather feedback from verifiers
2. **Analyze patterns**: Identify common issues and trends
3. **Create improvements**: Develop new prompts or modifications
4. **Test improvements**: Verify improvements work correctly
5. **Deploy improvements**: Update the operator prompt
6. **Monitor impact**: Track the effects of improvements

### Improvement Categories

#### Prompt Evolution
- Wording improvements
- Instruction refinements
- Example additions
- Constraint updates

#### Technical Improvements
- Performance optimizations
- Error handling enhancements
- New feature additions
- Bug fixes

#### Documentation Improvements
- Better user guides
- More examples
- Improved error messages
- Enhanced help text

## Quality Assurance

### Testing Standards

#### Unit Testing
- Test verifier functionality
- Validate scoring algorithms
- Test recommendation generation
- Verify error handling

#### Integration Testing
- Test with actual model responses
- Validate end-to-end workflow
- Test with various providers
- Verify cross-platform compatibility

#### Performance Testing
- Test with large payloads
- Validate response times
- Test resource usage
- Verify scalability

### Quality Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Accuracy | >95% | Correct scoring and validation |
| Response Time | <1s | Fast verification processing |
| Resource Usage | <10MB | Minimal memory footprint |
| Coverage | 100% | Comprehensive test coverage |
| Reliability | >99% | High availability and uptime |

## Configuration

### Verifier Settings

```toml
[verifier]
# Scoring thresholds
min_overall_score = 70.0
min_prompt_clarity = 80.0
min_response_relevance = 80.0

# Test settings
test_count = 100
retry_attempts = 3

# Improvement settings
auto_implement = false
rollback_on_failure = true

# Logging
log_level = "INFO"
log_file = "verifier.log"
```

## Security Considerations

### Adversarial Protection
- Test against known attack vectors
- Implement input validation
- Use secure communication protocols
- Monitor for suspicious activity

### Data Protection
- Encrypt sensitive data
- Implement proper access controls
- Regular security audits
- Patch management

## Performance Optimization

### Verifier Optimization
- Cache scoring results
- Implement parallel processing
- Use efficient data structures
- Optimize for speed and resource usage

### Test Optimization
- Run tests in parallel
- Use efficient test frameworks
- Implement smart sampling
- Cache test results

## Future Evolution

### New Verifier Features
- Machine learning-based scoring
- Automated test generation
- Predictive analytics
- Adaptive testing

### Advanced Testing
- Penetration testing
- Stress testing
- Load testing
- Security testing

## References

- PI harness principles
- Adversarial testing best practices
- Quality assurance methodologies
- Continuous improvement frameworks
- Security testing guidelines
- Performance optimization techniques

## Contact

For questions or issues with this verifier agent, please refer to the documentation or contact the codelaboon maintainers.
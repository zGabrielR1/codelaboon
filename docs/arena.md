# Arena — codelaboon

Arena fan-out — Step 5 expansion into N independent solvers + a judge, with routing triggers and degradation rules for codelaboon.

## Purpose

This document defines the arena system for codelaboon, an arena fan-out system that expands into N independent operator instances on one locked task, then a verifier acting as judge over anonymized candidates. The arena follows the PI harness principles and provides a structured approach to parallel model evaluation.

## The Arena System

The codelaboon arena system operates as follows:

1. **Task Locking**: Lock the exact task prompt for the arena
2. **Agent Spawning**: Spawn N independent operator instances in parallel
3. **Solution Collection**: Collect all solutions from the agents
4. **Judge Evaluation**: Have a judge evaluate and rank the solutions
5. **Result Presentation**: Present the ranked results to the user
6. **Decision Making**: Wait for user choice before applying changes

## Arena System

### Arena Configuration

#### Arena Configuration Process

1. **Configure Arena Size**: Set the number of agents (N)
2. **Configure Strategy**: Set the evaluation strategy
3. **Configure Models**: Set models for solvers and judge
4. **Configure Rules**: Set rules for the arena

**Arena configuration format:**
```
Arena Configuration:
- Arena Size: [number] agents
- Strategy: [judge/main/tournament]
- Solver Model: [model name]
- Judge Model: [model name]
- Rules: [list of rules]
- Routing Triggers: [list of triggers]
- Degradation Rules: [list of rules]
```

#### Configuration Process

1. **Set Arena Size**: Configure the number of agents
2. **Set Strategy**: Configure the evaluation strategy
3. **Set Models**: Configure models for solvers and judge
4. **Set Rules**: Configure rules for the arena

**Configuration process:**

1. **Configure Arena Size**: Set the number of agents (N)
2. **Configure Strategy**: Set the evaluation strategy
3. **Configure Models**: Set models for solvers and judge
4. **Configure Rules**: Set rules for the arena

### Agent Spawning

#### Agent Spawning Process

1. **Lock Task Prompt**: Lock the exact task prompt for the arena
2. **Configure Solvers**: Configure solver agents with the task
3. **Spawn Solvers**: Spawn solver agents in parallel
4. **Configure Judge**: Configure judge agent with the task
5. **Spawn Judge**: Spawn judge agent

**Agent spawning format:**
```
Agent Spawning Results:
- Solvers Spawned: [number] agents
- Judge Spawned: [judge agent]
- Task Locked: [task prompt]
- Solvers Configured: [solver configuration]
- Judge Configured: [judge configuration]
```

#### Spawning Process

1. **Lock Task**: Lock the exact task prompt
2. **Configure Solvers**: Configure solver agents
3. **Spawn Solvers**: Spawn solver agents in parallel
4. **Configure Judge**: Configure judge agent
5. **Spawn Judge**: Spawn judge agent

**Spawning process:**

1. **Lock Task**: Lock the exact task prompt
2. **Configure Solvers**: Configure solver agents with the task
3. **Spawn Solvers**: Spawn solver agents in parallel
4. **Configure Judge**: Configure judge agent with the task
5. **Spawn Judge**: Spawn judge agent

### Solution Collection

#### Solution Collection Process

1. **Collect Solutions**: Collect solutions from all solver agents
2. **Anonymize Solutions**: Anonymize solutions for judging
3. **Validate Solutions**: Validate solutions
4. **Organize Solutions**: Organize solutions for judging

**Solution collection format:**
```
Solution Collection Results:
- Solutions Collected: [number] solutions
- Solutions Anonymized: [anonymized solutions]
- Solutions Validated: [validated solutions]
- Solutions Organized: [organized solutions]
```

#### Collection Process

1. **Collect Solutions**: Collect solutions from all solver agents
2. **Anonymize Solutions**: Anonymize solutions for judging
3. **Validate Solutions**: Validate solutions
4. **Organize Solutions**: Organize solutions for judging

**Collection process:**

1. **Collect Solutions**: Collect solutions from all solver agents
2. **Anonymize Solutions**: Anonymize solutions for judging
3. **Validate Solutions**: Validate solutions
4. **Organize Solutions**: Organize solutions for judging

### Judge Evaluation

#### Judge Evaluation Process

1. **Configure Judge**: Configure judge agent with task and solutions
2. **Evaluate Solutions**: Judge evaluates solutions
3. **Score Solutions**: Score solutions based on evaluation
4. **Rank Solutions**: Rank solutions based on scores
5. **Provide Feedback**: Judge provides feedback

**Judge evaluation format:**
```
Judge Evaluation Results:
- Judge Configured: [judge agent]
- Solutions Evaluated: [number] solutions
- Solutions Scored: [scored solutions]
- Solutions Ranked: [ranked solutions]
- Feedback Provided: [feedback]
```

#### Evaluation Process

1. **Configure Judge**: Configure judge agent with task and solutions
2. **Evaluate Solutions**: Judge evaluates solutions
3. **Score Solutions**: Score solutions based on evaluation
4. **Rank Solutions**: Rank solutions based on scores
5. **Provide Feedback**: Judge provides feedback

**Evaluation process:**

1. **Configure Judge**: Configure judge agent with task and solutions
2. **Evaluate Solutions**: Judge evaluates solutions
3. **Score Solutions**: Score solutions based on evaluation
4. **Rank Solutions**: Rank solutions based on scores
5. **Provide Feedback**: Judge provides feedback

### Result Presentation

#### Result Presentation Process

1. **Format Results**: Format results for user consumption
2. **Present Ranking**: Present ranked list of solutions
3. **Provide Summaries**: Provide summaries of each solution
4. **Show Differences**: Show key differences between solutions
5. **Make Recommendation**: Make explicit recommendation
6. **Request Decision**: Request user choice before applying changes

**Result presentation format:**
```
Arena Results:
- Strategy: [strategy]
- n: [number of agents]
- Ranking:
  1. [Solution A] - [score] - [reason]
  2. [Solution B] - [score] - [reason]
  ...
- Summaries:
  - Solution A: [summary]
  - Solution B: [summary]
  - ...
- Key Differences:
  - Difference 1: [description]
  - Difference 2: [description]
- Recommendation:
  - Recommended Solution: [solution]
  - Reason: [reason]
- Decision Required: [yes/no]
```

#### Presentation Process

1. **Format Results**: Format results for user consumption
2. **Present Ranking**: Present ranked list of solutions
3. **Provide Summaries**: Provide summaries of each solution
4. **Show Differences**: Show key differences between solutions
5. **Make Recommendation**: Make explicit recommendation
6. **Request Decision**: Request user choice before applying changes

**Presentation process:**

1. **Format Results**: Format results for user consumption
2. **Present Ranking**: Present ranked list of solutions
3. **Provide Summaries**: Provide summaries of each solution
4. **Show Differences**: Show key differences between solutions
5. **Make Recommendation**: Make explicit recommendation
6. **Request Decision**: Request user choice before applying changes

### Decision Making

#### Decision Making Process

1. **Present Results**: Present results to the user
2. **Request Decision**: Request user choice before applying changes
3. **Validate Decision**: Validate user decision
4. **Apply Decision**: Apply the chosen solution
5. **Update State**: Update state with the applied solution

**Decision making format:**
```
Decision Making Results:
- Results Presented: [results]
- Decision Requested: [decision]
- Decision Validated: [valid/invalid] - [reason]
- Decision Applied: [solution]
- State Updated: [state]
```

#### Decision Process

1. **Present Results**: Present results to the user
2. **Request Decision**: Request user choice before applying changes
3. **Validate Decision**: Validate user decision
4. **Apply Decision**: Apply the chosen solution
5. **Update State**: Update state with the applied solution

**Decision process:**

1. **Present Results**: Present results to the user
2. **Request Decision**: Request user choice before applying changes
3. **Validate Decision**: Validate user decision
4. **Apply Decision**: Apply the chosen solution
5. **Update State**: Update state with the applied solution

## Arena Strategies

### Strategy: Judge (Default)

**Purpose**: Best for most cases. Clean separation of generation and evaluation.

**Steps**:

1. **Lock the exact task prompt**: Lock the exact task prompt for the arena
2. **Spawn N independent solver subagents**: Spawn N independent solver subagents in parallel using the chosen solver-model
3. **Collect solver results**: Each solver returns:
   - Approach summary (2-4 sentences)
   - The actual solution (code / plan / diff)
   - Self-assessed confidence (1-5) and main risks
4. **Spawn Judge subagent**: After all solvers finish, spawn one Judge subagent using the chosen judge-model
5. **Give Judge the information**: Give the Judge:
   - The original task
   - The scoring rubric
   - All solutions, anonymized as Solution A, B, C…
6. **Instruct Judge**: Instruct the Judge to return a ranked list with clear reasons for each ranking decision
7. **Present ranking**: Present the Judge's ranking to the user in a clean, readable format
8. **Wait for user choice**: Wait for user choice before applying any changes

### Strategy: Main

**Purpose**: Best for lower cost or when you want the orchestrator (you) to stay fully in control of the evaluation.

**Steps**:

1. **Lock the exact task prompt**: Lock the exact task prompt for the arena
2. **Spawn N independent solver subagents**: Spawn N independent solver subagents in parallel using the chosen solver-model
3. **Collect all results**: Collect all results from solvers
4. **Evaluate and rank**: Evaluate and rank them yourself using the scoring rubric
5. **Present ranked list**: Present the ranked list + recommendation to the user
6. **Wait for user choice**: Wait for user choice before applying any changes

### Strategy: Tournament

**Purpose**: Best for high-stakes decisions or when you want solutions to stress-test each other.

**Steps**:

1. **Lock the exact task prompt**: Lock the exact task prompt for the arena
2. **Spawn N independent solver subagents**: Spawn N independent solver subagents in parallel using the chosen solver-model
3. **Run a simple tournament**:
   - If N is even, pair them randomly. If odd, give one a bye.
   - For each pair, have a short critique (you or a small critic subagent) compare the two solutions side-by-side and declare a winner with 2–3 concrete reasons.
   - Optionally run one more ranking pass on the winners (or full set) using the scoring rubric
4. **Produce the final ranking**: Produce the final ranking from the critique outcomes + rubric
5. **Present tournament insights**: Present the tournament insights + final ranking + recommendation to the user
6. **Wait for user choice**: Wait for user choice before applying any changes

### Default Scoring Rubric

Use this rubric unless the user supplies a different one. Weight roughly:

| Criterion | Weight | Notes |
|-----------|--------|-------------|
| Correctness / completeness | High | Does it fully solve the stated task? |
| Compatibility / non-breaking | High | Especially important for refactors |
| Minimal & focused change | Medium | Prefer smaller, targeted diffs when quality is equal |
| Clarity & maintainability | Medium | Readable, well-structured, good names |
| Risk / side-effect surface | Medium | Fewer new failure modes is better |
| Plan adherence (if a plan exists) | Medium | Stays faithful to any agreed design |

## Arena Rules

### Rule: Identical Task

**Rule**: Every solver receives the *exact same* locked task prompt. Do not let solvers see each other's work or intermediate files.

**Implementation**:
1. Lock the exact task prompt
2. Ensure all solvers receive the identical task
3. Prevent solvers from accessing each other's work
4. Maintain task isolation

### Rule: Isolation

**Rule**: Prefer worktree isolation when the task involves writing or editing code so solvers cannot conflict.

**Implementation**:
1. Use worktree isolation for code-writing tasks
2. Prevent file system conflicts between solvers
3. Maintain isolation during execution
4. Ensure clean separation

### Rule: Anonymization for Judging

**Rule**: When a judge sees multiple solutions, present them as Solution A, B, C… with no agent identity.

**Implementation**:
1. Anonymize all solver solutions
2. Remove agent identity information
3. Present as generic solutions
4. Maintain anonymity

### Rule: No Automatic Commit

**Rule**: Never apply code changes until the user explicitly approves a candidate.

**Implementation**:
1. Do not automatically apply changes
2. Wait for user approval
3. Only apply after explicit user request
4. Maintain user control

### Rule: Clear Output

**Rule**: Always return:
- Ranked list (best first)
- Short summary of each approach
- Key differences between the top candidates
- Explicit recommendation + why
- Ask the user which one to apply (or confirm auto-apply if they already requested it)

## Arena Routing

### Routing Triggers

#### Trigger Types

1. **Task Trigger**: Trigger when a specific task is assigned
2. **Model Trigger**: Trigger when a specific model is selected
3. **Strategy Trigger**: Trigger when a specific strategy is chosen
4. **Resource Trigger**: Trigger when resources are available

**Routing trigger format:**
```
Routing Triggers:
- Task Trigger: [condition] -> [action]
- Model Trigger: [condition] -> [action]
- Strategy Trigger: [condition] -> [action]
- Resource Trigger: [condition] -> [action]
```

#### Routing Process

1. **Check Triggers**: Check all routing triggers
2. **Evaluate Conditions**: Evaluate trigger conditions
3. **Execute Actions**: Execute matching actions
4. **Update State**: Update state based on actions

**Routing process:**

1. **Check Triggers**: Check all routing triggers
2. **Evaluate Conditions**: Evaluate trigger conditions
3. **Execute Actions**: Execute matching actions
4. **Update State**: Update state based on actions

### Degradation Rules

#### Degradation Rule Types

1. **Fallback Rule**: Fallback to alternative approach
2. **Reduction Rule**: Reduce arena size or complexity
3. **Replacement Rule**: Replace model with alternative
4. **Suspension Rule**: Suspend arena operation

**Degradation rule format:**
```
Degradation Rules:
- Fallback Rule: [condition] -> [alternative action]
- Reduction Rule: [condition] -> [reduce action]
- Replacement Rule: [condition] -> [replace action]
- Suspension Rule: [condition] -> [suspend action]
```

#### Degradation Process

1. **Check Degradation Conditions**: Check all degradation conditions
2. **Apply Degradation Rules**: Apply matching degradation rules
3. **Update State**: Update state based on degradation
4. **Notify User**: Notify user about degradation

**Degradation process:**

1. **Check Degradation Conditions**: Check all degradation conditions
2. **Apply Degradation Rules**: Apply matching degradation rules
3. **Update State**: Update state based on degradation
4. **Notify User**: Notify user about degradation

## Implementation

### Data Structures

```python
class Arena:
    def __init__(self, task, n=4, strategy="judge", solver_model=None, judge_model=None):
        self.task = task
        self.n = n
        self.strategy = strategy
        self.solver_model = solver_model
        self.judge_model = judge_model
        self.solvers = []
        self.judge = None
        self.solutions = []
        self.results = None
    
    def to_dict(self):
        return {
            "task": self.task,
            "n": self.n,
            "strategy": self.strategy,
            "solver_model": self.solver_model,
            "judge_model": self.judge_model,
            "solvers": [solver.to_dict() for solver in self.solvers],
            "judge": self.judge.to_dict() if self.judge else None,
            "solutions": self.solutions,
            "results": self.results
        }
```

### Configuration

```toml
[arena]
# Arena settings
auto_spawn = true
auto_evaluate = true
auto_present = true
wait_for_user = true

# Arena configuration
max_agents = 6
min_agents = 2
default_strategy = "judge"
default_solver_model = "gpt-3.5-turbo"
default_judge_model = "gpt-4"

# Arena rules
identical_task = true
isolation = true
anonymization = true
no_auto_commit = true
clear_output = true

# Routing
routing_triggers = [
    { "condition": "task_trigger", "action": "spawn_agents" },
    { "condition": "model_trigger", "action": "select_model" },
    { "condition": "strategy_trigger", "action": "select_strategy" },
    { "condition": "resource_trigger", "action": "allocate_resources" }
]

# Degradation
degradation_rules = [
    { "condition": "resource_limited", "action": "reduce_agents" },
    { "condition": "model_unavailable", "action": "replace_model" },
    { "condition": "time_limited", "action": "suspend_arena" }
]
```

## Quality Assurance

### Arena Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Arena Setup Success | 100% | Arena setup completed successfully |
| Agent Spawning Success | 100% | All agents spawned successfully |
| Solution Collection Success | 100% | All solutions collected successfully |
| Judge Evaluation Success | 100% | Judge evaluation completed successfully |
| Result Presentation Success | 100% | Results presented successfully |
| Decision Making Success | 100% | Decision making completed successfully |

## Security Considerations

### Arena Security
- Validate arena configuration
- Use secure agent spawning
- Implement solution isolation
- Protect user data

### Data Protection
- Encrypt arena data
- Implement data retention policies
- Protect user privacy
- Ensure compliance with regulations

## Performance Optimization

### Arena Optimization
- Use efficient agent spawning
- Implement smart resource allocation
- Optimize for parallel processing
- Minimize overhead

### Evaluation Optimization
- Use efficient evaluation algorithms
- Implement smart caching
- Optimize for speed
- Minimize resource usage

## Future Evolution

### New Arena Features
- Machine learning-based agent selection
- Automated strategy selection
- Predictive performance optimization
- Adaptive resource allocation

### Advanced Arena Techniques
- Natural language processing for task understanding
- Machine learning for solution evaluation
- Automated solution generation
- Solution anomaly detection

## Integration with Other Systems

### Integration Points

1. **Task System**: Integrate with task management system
2. **Agent System**: Integrate with agent management system
3. **Evaluation System**: Integrate with evaluation system
4. **Decision System**: Integrate with decision making system

### Cross-System Benefits

#### Improved Model Evaluation
- Better parallel evaluation
- Enhanced solution quality
- Improved performance
- Better resource utilization

#### Enhanced User Experience
- Better result presentation
- Improved decision making
- Enhanced user control
- Better feedback

## References

- PI harness principles
- Arena management best practices
- Parallel processing techniques
- Natural language processing for task understanding
- Machine learning for solution evaluation
- Performance optimization techniques
- Security best practices
- Data protection guidelines
- Agent management methodologies

## Contact

For questions or issues with the arena system, please refer to the documentation or contact the codelaboon maintainers.
# Assignment 1: Collaborative Agentic Workflow with GitHub

## Objective

In this assignment, you will work in **pairs** to build an **AI agentic workflow** while practicing professional software collaboration using **GitHub**.

The goal is not only to build an AI application, but also to experience how software teams collaborate using feature branches, pull requests, code reviews, and merge requests.

---

# Scenario

Your team has been hired to build a **Meeting Preparation AI Agent**.

Given a meeting topic, the agent should automatically prepare a concise briefing document that helps a user get ready for an upcoming meeting.

Example input:

> "Prepare me for a meeting about adopting AI for customer support."

Example output:

- Meeting summary
- Background information
- Benefits
- Risks
- Questions to ask
- Final recommendation

---

# Functional Requirements

Your workflow should perform the following steps.

```
User
   │
   ▼
Planner Agent
   │
   ▼
Research Tool
   │
   ▼
Question Generator
   │
   ▼
Risk Analyzer
   │
   ▼
Reviewer Agent
   │
   ▼
Final Meeting Brief
```

---

# Minimum Requirements

Your workflow must include:

- At least **2 AI agents**
- At least **1 tool**
- A workflow connecting the agents together
- One decision made by the agent

Example:

- If the request is vague → ask a clarification question
- If the topic is technical → perform research
- If a document exists → use the document reader
- Otherwise → skip research

---

# Team Responsibilities

Divide the work between both members.

---

## Student A

Responsible for:

- Planner Agent
- Research Tool
- Research Agent
- Input validation

Suggested files:

```
agents/planner.py

agents/researcher.py

tools/search.py
```

---

## Student B

Responsible for:

- Question Generator
- Risk Analyzer
- Reviewer Agent
- Final report formatter

Suggested files:

```
agents/questions.py

agents/reviewer.py

workflow/report.py
```

---

# Shared Data Structure

Before writing code, both students should agree on a common data structure.

Example:

```python
meeting = {
    "topic": "",
    "goal": "",
    "research": "",
    "questions": [],
    "risks": [],
    "recommendation": "",
    "summary": ""
}
```

This interface should remain consistent throughout the project.

---

# GitHub Collaboration Requirements

Each student must:

- Create their own branch
- Work only on their assigned feature
- Commit frequently
- Push commits to GitHub
- Open a Pull Request
- Review the other student's Pull Request
- Request at least one improvement
- Resolve merge conflicts (if any)
- Merge only after approval

Suggested branches:

```
feature/planner

feature/reviewer
```

---

# Suggested Project Structure

```
meeting-prep-agent/

│
├── README.md
├── requirements.txt
├── main.py
│
├── agents/
│   ├── planner.py
│   ├── researcher.py
│   ├── questions.py
│   └── reviewer.py
│
├── tools/
│   └── search.py
│
├── workflow/
│   └── pipeline.py
│
└── tests/
    └── test_pipeline.py
```

---

# Expected Workflow

Example:

```
User:
Prepare me for a meeting on AI governance

↓

Planner decides:
Research is needed

↓

Research tool gathers information

↓

Question Generator creates discussion questions

↓

Risk Analyzer identifies concerns

↓

Reviewer checks completeness

↓

Final meeting brief returned
```

---

# Stretch Goal

Add a reviewer loop.

Example:

```
Draft Report

↓

Reviewer

↓

Score >= 8?

      Yes
       │
       ▼
Return Report

      No
       │
       ▼
Revise Report
```

---

# Mid-Assignment Change Request

Halfway through development, your instructor will introduce a new requirement.

Example:

> The agent must now accept a company policy document and ensure that its recommendations align with that document.

Your team should:

- Create a new GitHub issue
- Decide how to split the work
- Modify the existing workflow
- Open new Pull Requests
- Merge the changes successfully

This simulates a real software development environment where requirements evolve over time.

---

# Deliverables

Submit:

- GitHub Repository
- Working application
- README explaining the architecture
- Pull Requests from both students
- Evidence of code reviews

---

# Evaluation Rubric

| Category | Points |
|----------|--------|
| Agentic workflow | 25 |
| Tool integration | 15 |
| Workflow architecture | 15 |
| Code quality | 15 |
| GitHub collaboration | 20 |
| Documentation | 10 |

**Total: 100 points**

---

# Bonus (Optional)

Add one of the following:

- Web Search Tool
- PDF Reader Tool
- Local Document Search
- Memory between agent steps
- Logging or tracing
- Retry logic if an agent fails

---

# Learning Objectives

By the end of this assignment, you should be able to:

- Build a simple agentic AI workflow
- Connect multiple AI agents together
- Use tools within an AI workflow
- Collaborate using GitHub
- Work with feature branches
- Review code through Pull Requests
- Integrate independently developed components into a complete application

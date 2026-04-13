---
description: [SHORT TITLE OF THE WORKFLOW]
---

# [WORKFLOW TITLE]

> **Contextual Agent Protocol**
>
> - **Identity:** You are [AGENT NAME], a specialized [DOMAIN EXPERT ROLE].
> - **Purpose:** Your sole purpose is to generate [SPECIFIC OUTPUT].
> - **Process:** You will begin by conducting a hard analysis of the attached information/documents. Your output must be a synthesis of the specific training materials, target, context, and resources provided.
> - **Constraints:** You must adhere strictly and exclusively to the methodologies, frameworks, and examples contained within this context.
> - **Objective:** Your primary objective is to generate [ADJECTIVE] and [ADJECTIVE] [OUTPUT] explicitly grounded in the provided training examples, prioritizing [KEY PRIORITY 1] and strict adherence to [KEY PRIORITY 2].
>
> **Cognitive Framework**
>
> 1. **Identify and Analyze Provided Information:** Clearly determine whether the provided data relates to [Category 1], [Category 2], or other indicators.
> 2. **Extract Key Principles:** Identify principles including: [Principle 1], [Principle 2]. Capture specific needs based on [Relevant Context].
> 3. **Ensure Consistency:** Align recommendations strictly with [Type of Input]. If outside data, state: "This information is not available in the provided data".
> 4. **Reinforce Comprehensive Integration:** Upon receiving new [Type of Input], summarize findings and reference them in future outputs.
> 5. **Structured Output Approach:**
>    1. Introduction (Summary)
>    2. Core Recommendations
>    3. Detailed Breakdown
>    4. Additional Recommendations
>    5. Explicit Rationale
> 6. **Comprehensive Integration:** Integrate all relevant insights from [Type of Input] without oversimplification.
> 7. **Contextual Layering:** Combine principles to deliver comprehensive outputs.
> 8. **Edge Cases:** Identify challenges and provide adaptation strategies.
> 9. **Address Pain Points:** Directly use identified pain points to reinforce value.
> 10. **Utilize Provided Data Exclusively:** Avoid fabricating recommendations.
> 11. **Logical Flow:** Verify accuracy and alignment at every stage.
> 12. **Consistent Tone:** Maintain a clear, precise, and supportive tone.

---

## Phase 1: [PHASE NAME]

1. **[Step Name]**
   - [ ] [Step Instruction]

## Phase 2: [PHASE NAME]

1. **[Step Name]**
   - [ ] [Step Instruction]

## Phase 3: Testing & Quality Assurance (MANDATORY)

1. **Test Environment Preparation**
   - [ ] Identify external dependencies (MongoDB, WhatsApp API, LLMs) and set up necessary mocks or test databases using established Django patterns.
   - [ ] Ensure co-location of tests (e.g., `tests/` directory or `test_*.py` files).

2. **Automated Test Creation**
   - [ ] Create unit tests for business logic, Python utilities, and custom Agentic Tools (CrewAI).
   - [ ] Create integration tests for Django API routes (DRF Views), covering:
     - [ ] **Success Path:** Verify 200 OK and expected API format.
     - [ ] **Background Execution:** Verify webhook views return 200 OK immediately and hand off heavy logic (like Agent execution) to threads/Celery.
     - [ ] **Error Handling:** Verify appropriate 400/500 responses for invalid inputs or external service timeouts.

3. **Verification & Validation**
   - [ ] Run `python manage.py test` or `pytest` and ensure all new tests pass.
   - [ ] Check logs for Agent execution transparency when utilizing CrewAI.
   - [ ] Validate PEP 8 compliance for Python code.

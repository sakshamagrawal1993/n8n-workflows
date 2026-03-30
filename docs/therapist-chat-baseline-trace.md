# Mind Coach Therapist Chat Baseline Trace

This documents the runtime chain for `mind-coach-therapist-chat-and-discovery-v6-robust`.

## 1) Webhook Input (expected fields)

The workflow starts at `Webhook` and reads either `body` or top-level JSON.

Primary fields consumed by `Prompt Builder`:

- `profile_id`, `session_id`
- `profile` (`name`, `age`, `gender`, `concerns`)
- `message_text` (latest user turn)
- `messages` (recent transcript, last 10-15 turns)
- `memories` (consolidated memory rows)
- `recent_tasks_assigned`
- `dynamic_theme`
- `coach_prompt`
- `phase_prompt`
- `message_count`
- `is_system_greeting`
- `session_state`
- `pathway`

## 2) Core Execution Chain

1. `Webhook`
2. `Crisis Screening Agent`
3. `Is Crisis?`
4. Crisis path: `Return Crisis Alert` (terminal)
5. Non-crisis path:
   - `Prompt Builder`
   - `Therapist Agent` + `Therapist Model` + `Therapist Output Parser`
   - `Is Assessment Phase?`
   - Optional discovery branch: `Discovery Agent` + `Discovery Model` + `Discovery Output Parser`
   - `Format Final Response`
   - `Respond to Webhook`

## 3) Prompt Builder Outputs

`Prompt Builder` emits:

- `systemPrompt` (coach + phase + memory + transcript + cadence rules + output contract)
- `userMessage`
- `profileId`, `sessionId`
- `messageCount`
- `shouldRunDiscovery` (true at configured turns)
- `promptSignals`:
  - `asksForStructuredPlan`
  - `elevatedDistressDetected`
  - `repeatedConcern`
  - `repeatedTherapistOpeners`

## 4) Therapist Agent Output Contract

Required fields remain unchanged:

- `reply` (string)
- `is_session_close` (boolean)
- `dynamic_in_chat_exercise` (string|null)

Optional fields:

- `dynamic_content` (`type`: `exercise|exercise_card`, `payload`: string)
- `quality_meta` (optional quality diagnostics and strategy labels)

The parser accepts both:

- direct object shape, or
- wrapper shape under `output`.

## 5) Final Response Composition

`Format Final Response` returns normalized JSON:

- always includes required chat fields
- normalizes `dynamic_content.type: exercise_card -> exercise`
- keeps discovery fields when present (`dynamic_theme`, `suggested_pathway`, `pathway_confidence`)
- passes through optional `quality_meta` when present

This keeps backward compatibility for existing frontend and edge-function consumers.

## 6) Field Feedback: Current Pain Points

Based on colleague testing, the current workflow behavior needs improvement in four areas:

1. Responses are often too long and harder to scan.
2. Therapist voice overuses acknowledgement fillers (for example, "Thank you for sharing...").
3. End-to-end response time is often too slow.
4. Early-session quick in-chat exercises are under-recommended in general chat.

Additional product requirement:

- The assistant should provide longer responses when the user explicitly asks for a plan.

## 7) Root-Cause Analysis

### A) Long responses

- Therapist model configuration allows long outputs (`maxTokens` currently high).
- Prompt builder currently permits expansive structures in normal chat.
- No hard distinction between normal-chat brevity and plan-request verbosity.

### B) Acknowledgement fluff

- Cadence guidance nudges validation language too often.
- Repetition controls are not strict enough to prevent stock opener reuse.

### C) Slow responses

- Hot path executes multiple serial model calls:
  - crisis screen first,
  - therapist generation,
  - discovery branch on selected turns.
- Discovery currently runs inline when triggered, adding avoidable latency.

### D) Low early exercise recommendation rate

- Exercise trigger window is too narrow and brittle.
- Gating relies on strict acknowledgement/keyword patterns.
- Prior exercise detection can suppress early-session offers too aggressively.

## 8) Recommended Design Direction

Use a phased architecture change instead of a one-step hard split:

1. Keep crisis screening synchronous and safety-first.
2. Keep therapist reply synchronous.
3. Move discovery to async/background update path.
4. Add explicit response modes:
   - `normal_chat` (concise)
   - `plan_request` (longer structured output)

This achieves quality and latency gains quickly while reducing migration risk.

## 9) Concrete Solution Plan by Issue

### Issue 1: Long responses

- Add response mode routing in Prompt Builder (`normal_chat` vs `plan_request`).
- For `normal_chat`, enforce concise reply budget (short paragraphs, single forward question).
- Reduce therapist model temperature and normal-mode token cap.
- Keep higher token budget only for explicit plan intent.

### Issue 2: Acknowledgement fluff

- Change cadence rule from mandatory validation-every-turn to conditional validation.
- Ban repeated stock openers across recent assistant turns.
- Require therapist responses to move conversation forward (reflection + next step).

### Issue 3: Slow responses

- Remove discovery from synchronous response path.
- Trigger discovery asynchronously after reply is returned.
- Add stage-level timing telemetry and set p50/p95 targets.
- Keep crisis path fail-safe and monitor for false negatives.

### Issue 4: Low early in-chat exercise recommendation

- Replace narrow turn-window trigger with stage-aware eligibility.
- Relax brittle acknowledgement dependencies in trigger logic.
- Add deterministic fallback: if early session and no exercise by threshold, offer one quick exercise.
- Improve exercise-history detection to be session-aware and reliable.

## 10) Build Task List (Execution Backlog)

Use this checklist as the implementation queue.

### P0 - High Impact / Low-Medium Risk

- [ ] `T-001` Add prompt response modes (`normal_chat`, `plan_request`) in `Prompt Builder`.
- [ ] `T-002` Tune therapist defaults for concise chat (`maxTokens`, `temperature`).
- [ ] `T-003` Replace mandatory validation cadence with conditional validation.
- [ ] `T-004` Add anti-repetition guard for acknowledgement stock openers.
- [ ] `T-005` Add stage-level latency instrumentation in edge (`mind-coach-chat`).
- [ ] `T-006` Broaden early exercise eligibility (remove narrow turn cliff).

### P1 - High Impact / Medium Risk

- [ ] `T-007` Move discovery to async path and persist updates post-reply.
- [ ] `T-008` Add fallback contract-safe response for parser/prompt-builder failures.
- [ ] `T-009` Improve session-scoped exercise history detection.
- [ ] `T-010` Add deterministic early-exercise fallback when policy says "should offer."

### P2 - Hardening and Rollout

- [ ] `T-011` Add scenario matrix tests (normal, plan, distress, crisis, early-session exercise).
- [ ] `T-012` Validate KPI gates (length, fluff frequency, p50/p95 latency, exercise uplift).
- [ ] `T-013` Stage rollout with feature flags and rollback toggles.

## 11) Suggested Owners

- n8n workflow changes: Prompt Builder, Therapist model, discovery routing, formatter hardening.
- Edge changes: telemetry, async discovery orchestration, contract-safe fallbacks.
- QA/Clinical review: response quality, tone safety, crisis safety non-regression.

## 12) Success Metrics

- Median normal-chat response length reduced.
- Repetitive acknowledgement phrase frequency reduced.
- p50/p95 response latency reduced.
- Early-session exercise recommendation rate increased.
- No crisis handling regressions.

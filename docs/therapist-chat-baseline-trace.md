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

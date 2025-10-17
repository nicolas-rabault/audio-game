# Feature Specification: Optional TOOLS Variable for Character Function Calling

**Feature Branch**: `003-on-characters-i`
**Created**: 2025-10-17
**Status**: Draft
**Input**: User description: "on characters I want to add a TOOLS variables.  This variable have to be optonal and descripbe the various tools using function calling that can be triggered by the LLM. I would like you to make a dummy tool description on the narrator.py character triggering a simple log on the terimnal. The function called need to be implemented in the character .py file. The LLM code part should ask the character code part to call the function if the Model try to use one of the tool."

## Clarifications

### Session 2025-10-17

- Q: When a tool function throws an error during execution, how should the system respond? → A: Log error to terminal/logs, return error message to LLM so it can respond appropriately to user
- Q: When a character defines a TOOLS variable but doesn't implement the corresponding tool handler functions, what should happen? → A: Reject character loading at startup with clear error message identifying missing implementations
- Q: How should the system handle tool calls when the LLM specifies invalid parameters or calls a non-existent tool name? → A: Validate parameters before execution; return descriptive error to LLM if validation fails
- Q: How should the system behave when TOOLS is defined but empty? → A: Allow character to load normally; treat as character without tools (no tools available to LLM)
- Q: What happens when the LLM attempts to call a tool but the character format (legacy vs embedded) doesn't support it? → A: Remove legacy format support entirely; only manage embedded format. Remove all code that manages legacy format.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Character Developer Adds Tool to Existing Character (Priority: P1)

A character developer wants to enhance an existing character (e.g., narrator.py) by adding tool-calling capabilities without modifying core system code. They define tools in the character file itself, and the LLM can trigger these tools during conversations.

**Why this priority**: This is the core value proposition - enabling character developers to extend character capabilities independently without system modifications. It's a fully self-contained feature that delivers immediate value.

**Independent Test**: Can be fully tested by adding a TOOLS variable to narrator.py with a simple logging tool, running a conversation, and verifying the tool gets called when the LLM decides to use it. No other features needed.

**Acceptance Scenarios**:

1. **Given** a character file (narrator.py) with a TOOLS variable defining a logging tool, **When** the LLM decides to use that tool during conversation, **Then** the tool function is executed and output appears in the terminal
2. **Given** a character file without a TOOLS variable, **When** the character is loaded, **Then** the system continues to function normally without tool-calling capabilities
3. **Given** a conversation is active with a tool-enabled character, **When** the LLM attempts to call a defined tool, **Then** the character's tool handler executes the function and returns results to the LLM

---

### User Story 2 - Character Developer Creates New Tool-Enabled Character (Priority: P2)

A character developer creates a new character from scratch that includes custom tools for specific interactions (e.g., a game master character with dice-rolling tools, a DJ character with music control tools).

**Why this priority**: This extends the feature to new character creation workflows, enabling richer character capabilities from the start. Depends on P1 infrastructure but adds documentation and patterns.

**Independent Test**: Create a new character file with TOOLS defined from the beginning, load it, and verify tools work in conversation. Success demonstrates the feature works for both new and existing characters.

**Acceptance Scenarios**:

1. **Given** a new character file with multiple tool definitions in TOOLS variable, **When** the character is loaded at server startup, **Then** all tools are registered and available for LLM use
2. **Given** a tool-enabled character is active, **When** multiple tools are available, **Then** the LLM can choose the appropriate tool based on conversation context

---

### User Story 3 - User Interacts with Tool-Enabled Character (Priority: P3)

An end user has a conversation with a tool-enabled character and experiences enhanced capabilities (e.g., the narrator can log story events, a quiz character can record scores) without knowing the technical implementation.

**Why this priority**: This validates the end-user experience and ensures tools enhance conversations naturally. It's the ultimate success metric but depends on P1 and P2 being complete.

**Independent Test**: Have a conversation with the narrator character and trigger the logging tool through natural dialogue. Verify the tool executes transparently and enhances the experience without breaking conversation flow.

**Acceptance Scenarios**:

1. **Given** a user is conversing with a tool-enabled character, **When** the conversation context triggers a tool call, **Then** the tool executes seamlessly without interrupting the conversation flow
2. **Given** a tool produces output (like terminal logs), **When** the tool completes, **Then** the LLM can acknowledge or incorporate the tool's result in its next response

---

### Edge Cases

- When a character defines a TOOLS variable but doesn't implement the corresponding tool handler functions: Character loading is rejected at startup with clear error message identifying missing implementations
- When the LLM specifies invalid parameters or calls a non-existent tool name: System validates parameters before execution and returns descriptive error to LLM if validation fails
- When a tool function throws an error during execution: System logs error to terminal/logs and returns error message to LLM so it can respond appropriately to the user
- When TOOLS is defined but empty: Character loads normally and is treated as character without tools (no tools available to LLM)
- Legacy character format is no longer supported: All legacy format code will be removed; only embedded format is supported

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support an optional TOOLS variable in character files that describes available tool functions; empty TOOLS variable MUST be treated as valid (character has no tools)
- **FR-002**: Character files MUST be able to define tool implementations within the same file where TOOLS is declared
- **FR-003**: System MUST provide a mechanism for LLM code to request tool execution from the character code when the model attempts to use a tool
- **FR-004**: Tool definitions MUST describe the tool's purpose, parameters (with types), and expected behavior using a standard function-calling format; system MUST validate tool call parameters against these definitions before execution and return descriptive errors to LLM for invalid calls
- **FR-005**: System MUST remove all legacy character format support code; only embedded character format is supported going forward
- **FR-006**: When a character has TOOLS defined, the LLM MUST be informed of available tools during prompt generation
- **FR-007**: System MUST handle tool execution errors gracefully without crashing the conversation; errors MUST be logged to terminal/logs and error messages MUST be returned to the LLM for appropriate user-facing responses
- **FR-008**: Tool implementations MUST be isolated within the character file (no modifications to core LLM or system code required)
- **FR-009**: System MUST validate that defined tools have corresponding implementation functions at character loading time; characters with missing tool implementations MUST be rejected with clear error messages identifying which implementations are missing
- **FR-010**: As a demonstration, narrator.py character MUST include a dummy logging tool that outputs to the terminal when triggered

### Key Entities

- **Tool Definition**: A description of a callable function including its name, purpose, parameters (with types and descriptions), and expected return format
- **Tool Implementation**: The actual function code that executes when the LLM requests the tool, implemented within the character file
- **Tool Request**: The LLM's decision to invoke a specific tool with specific parameters during a conversation
- **Tool Response**: The result returned from a tool execution that may be used by the LLM in subsequent responses

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Character developers can add custom capabilities to characters through isolated configuration changes without modifying core system
- **SC-002**: At least one working demonstration shows end-to-end tool capability integration
- **SC-003**: System only supports embedded character format after legacy format code removal (embedded characters without tools continue to function identically)
- **SC-004**: When a character uses a custom capability during conversation, the action completes and results are visible to users in the same session
- **SC-005**: Errors in custom capabilities are handled gracefully without interrupting user conversations

## Assumptions

- The existing character loading infrastructure (character_loader.py) can be simplified by removing legacy format support
- The LLM integration already supports or can be extended to support function calling (common in modern LLMs like GPT-4, Claude, etc.)
- Tool functions execute synchronously or the system can handle asynchronous tool execution
- Tools return string or serializable data that can be passed back to the LLM
- All existing characters have been or will be migrated to embedded format before this feature is deployed

## Scope

### In Scope

- Adding TOOLS variable support to embedded character file format
- Implementing tool handler interface in character files
- Integrating tool definitions into LLM prompts
- Creating tool execution pathway from LLM to character code
- Example implementation: narrator.py with terminal logging tool
- Error handling for tool execution failures
- Documentation of tool definition format
- Removing all legacy character format support code from the system

### Out of Scope

- Graphical UI for tool creation or management
- Tool marketplace or sharing mechanism
- Asynchronous or long-running tool execution (initial version assumes quick tool execution)
- Tool permissions or security sandboxing (assumes trusted character developers)
- Tool execution history or analytics
- Cross-character tool sharing
- Tool versioning or migration

## Dependencies

- Existing character loading system (character_loader.py) - will be simplified by removing legacy format support
- LLM integration that supports function calling or can be extended to support it
- All characters must be in embedded format (no legacy format characters)

## Risks

- **Risk**: Existing LLM integration may not support function calling, requiring significant modifications
  - **Mitigation**: Research current LLM integration capabilities early; use industry-standard function-calling patterns

- **Risk**: Tool execution errors could destabilize conversations or the server
  - **Mitigation**: Implement robust error handling and isolation for tool execution

- **Risk**: Character developers may create tools with unintended side effects
  - **Mitigation**: Document best practices; consider logging all tool executions for debugging

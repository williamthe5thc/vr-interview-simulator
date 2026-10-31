# 📊 VR Interview System - Architecture Flowcharts

## 🏗️ System Architecture Overview

```mermaid
graph TB
    subgraph "VR Client (Unity)"
        A[VR Headset] --> B[Unity Application]
        B --> C[WebSocket Client]
        B --> D[Audio Capture]
        B --> E[Avatar System]
        B --> F[UI System]
    end
    
    subgraph "Network Layer"
        G[WebSocket Connection<br/>Port 8765]
    end
    
    subgraph "Python Server"
        H[Enhanced Server] --> I[WebSocket Server]
        I --> J[State Manager]
        I --> K[Stream Processor]
        
        subgraph "Audio Services"
            L[STT Service<br/>(Whisper)]
            M[TTS Service<br/>(AllTalk/gTTS)]
        end
        
        subgraph "AI Services"
            N[LLM Client<br/>(Ollama)]
            O[Scenario Manager]
        end
        
        subgraph "Support Services"
            P[Error Handler]
            Q[Heartbeat Service]
            R[Cache Manager]
        end
    end
    
    subgraph "External Services"
        S[Ollama Server<br/>(Mistral LLM)]
        T[AllTalk TTS Server]
        U[CUDA/Whisper STT]
    end
    
    C -.->|WebSocket| G
    G -.->|WebSocket| I
    
    K --> L
    K --> M
    K --> N
    
    L --> U
    M --> T
    N --> S
    
    J --> P
    I --> Q
    N --> R
    
    style A fill:#e1f5fe
    style H fill:#c8e6c9
    style S fill:#fff3e0
    style T fill:#fff3e0
    style U fill:#fff3e0
```

## 🔄 Audio Processing Pipeline

```mermaid
graph TD
    A[User Speaks in VR] --> B[Unity Captures Audio]
    B --> C[Encode Base64]
    C --> D[Send via WebSocket]
    
    D --> E{Server Receives}
    E --> F[State: LISTENING]
    F --> G[Decode Audio Data]
    
    G --> H[State: PROCESSING_STT]
    H --> I[Whisper STT Processing]
    I --> J[Generate Transcript]
    
    J --> K[State: PROCESSING_LLM]
    K --> L[Format Context + Prompt]
    L --> M[Send to Ollama]
    M --> N[Generate AI Response]
    
    N --> O[State: PROCESSING_TTS]
    O --> P{TTS Method}
    
    P -->|Primary| Q[AllTalk TTS]
    P -->|Fallback| R[Google TTS]
    
    Q --> S[Generate Audio WAV]
    R --> S
    
    S --> T[State: RESPONDING]
    T --> U[Encode Base64]
    U --> V[Send via WebSocket]
    
    V --> W[Unity Receives]
    W --> X[Decode Audio]
    X --> Y[Play via Avatar]
    
    Y --> Z[State: WAITING]
    Z --> A
    
    style A fill:#e3f2fd
    style I fill:#fff3e0
    style M fill:#f3e5f5
    style S fill:#e8f5e8
    style Y fill:#e3f2fd
```

## 🎯 State Machine Flow

```mermaid
graph LR
    A[IDLE] -->|User starts speaking| B[LISTENING]
    B -->|Audio received| C[PROCESSING_STT]
    C -->|Transcript ready| D[PROCESSING_LLM]
    D -->|Response generated| E[PROCESSING_TTS]
    E -->|Audio ready| F[RESPONDING]
    F -->|Audio sent| G[WAITING]
    G -->|User speaks again| B
    G -->|Session timeout| A
    
    C -->|STT Error| H[ERROR]
    D -->|LLM Error| H
    E -->|TTS Error| H
    H -->|Recovery| G
    H -->|Reset| A
    
    style A fill:#c8e6c9
    style B fill:#bbdefb
    style C fill:#fff9c4
    style D fill:#f8bbd9
    style E fill:#d1c4e9
    style F fill:#b2dfdb
    style G fill:#dcedc8
    style H fill:#ffcdd2
```

## 🌐 WebSocket Communication Flow

```mermaid
sequenceDiagram
    participant VR as VR Client
    participant WS as WebSocket Server
    participant SM as State Manager
    participant AP as Audio Pipeline
    participant LLM as LLM Service
    participant TTS as TTS Service
    
    VR->>WS: Connect
    WS->>SM: Create Session
    WS->>VR: Session ID + IDLE State
    
    VR->>WS: Client Capabilities
    WS->>VR: Capabilities Acknowledged
    
    VR->>WS: Audio Data
    WS->>SM: Transition to LISTENING
    WS->>AP: Process Audio Pipeline
    
    AP->>SM: Transition to PROCESSING_STT
    AP->>AP: Whisper STT Processing
    
    AP->>SM: Transition to PROCESSING_LLM
    AP->>LLM: Generate Response
    LLM-->>AP: AI Response Text
    
    AP->>SM: Transition to PROCESSING_TTS
    AP->>TTS: Synthesize Speech
    TTS-->>AP: Audio Data
    
    AP->>SM: Transition to RESPONDING
    WS->>VR: Audio Response
    
    SM->>VR: State Update (WAITING)
    
    Note over VR,TTS: Process repeats for conversation
```

## 🧠 LLM Context Management

```mermaid
graph TD
    A[User Input] --> B[Load Session Context]
    B --> C[Format Conversation History]
    
    C --> D{Context Size Check}
    D -->|Too Large| E[Prune Context]
    D -->|OK| F[Build System Prompt]
    
    E --> G[Keep Important Turns]
    G --> H[Keep Recent Exchanges]
    H --> F
    
    F --> I[Add Role Reinforcement]
    I --> J[Add Stage Guidance]
    J --> K[Format Final Prompt]
    
    K --> L[Send to Ollama]
    L --> M[Generate Response]
    
    M --> N[Post-process Response]
    N --> O{Role Confusion Check}
    O -->|Detected| P[Use Fallback Response]
    O -->|Clean| Q[Cache Response]
    
    P --> R[Add to Session Context]
    Q --> R
    R --> S[Return to Pipeline]
    
    style A fill:#e3f2fd
    style L fill:#f3e5f5
    style O fill:#fff3e0
    style S fill:#e8f5e8
```

## 🔧 Error Handling & Recovery

```mermaid
graph TD
    A[Error Detected] --> B{Error Type}
    
    B -->|STT Error| C[STT Recovery]
    B -->|LLM Error| D[LLM Recovery]
    B -->|TTS Error| E[TTS Recovery]
    B -->|WebSocket Error| F[Connection Recovery]
    B -->|System Error| G[General Recovery]
    
    C --> H[Retry with Fallback]
    D --> I[Use Cached Response]
    E --> J[Try Alternative TTS]
    F --> K[Reconnection Logic]
    G --> L[Safe State Transition]
    
    H --> M{Recovery Success?}
    I --> M
    J --> M
    K --> M
    L --> M
    
    M -->|Yes| N[Continue Normal Flow]
    M -->|No| O[Escalate Error]
    
    O --> P[Transition to ERROR State]
    P --> Q[Send Error Message]
    Q --> R[Attempt Recovery]
    R --> S[Return to WAITING]
    
    style A fill:#ffcdd2
    style M fill:#fff9c4
    style N fill:#c8e6c9
    style S fill:#dcedc8
```

## 🏭 Production Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        A[Oculus Quest VR]
        B[Unity Application]
    end
    
    subgraph "Network & Security"
        C[WebSocket SSL/TLS]
        D[Firewall Rules]
        E[Load Balancer]
    end
    
    subgraph "Application Layer"
        F[VR Interview Server]
        G[Session Management]
        H[Audio Processing]
        I[State Management]
    end
    
    subgraph "Service Layer"
        J[Ollama LLM Service]
        K[AllTalk TTS Service]
        L[Whisper STT Service]
    end
    
    subgraph "Infrastructure"
        M[GPU Server<br/>(CUDA)]
        N[CPU Server<br/>(Processing)]
        O[Storage<br/>(Conversations)]
    end
    
    subgraph "Monitoring"
        P[Health Checks]
        Q[Performance Metrics]
        R[Error Logging]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    
    F --> G
    F --> H
    F --> I
    
    H --> J
    H --> K
    H --> L
    
    J --> M
    K --> N
    L --> M
    
    G --> O
    
    F --> P
    F --> Q
    F --> R
    
    style A fill:#e1f5fe
    style F fill:#c8e6c9
    style M fill:#fff3e0
    style P fill:#f3e5f5
```

## 📱 Component Interaction Matrix

```mermaid
graph LR
    subgraph "Core Components"
        A[Enhanced Server]
        B[WebSocket Server]
        C[State Manager]
        D[Stream Processor]
    end
    
    subgraph "Audio Services"
        E[STT Service]
        F[TTS Service]
    end
    
    subgraph "AI Services"
        G[LLM Client]
        H[Scenario Manager]
    end
    
    subgraph "Support Services"
        I[Error Handler]
        J[Heartbeat Service]
        K[Cache Manager]
    end
    
    A --> B
    B --> C
    B --> D
    
    D --> E
    D --> F
    D --> G
    
    G --> H
    
    C --> I
    B --> J
    G --> K
    F --> K
    
    I -.-> C
    I -.-> D
    J -.-> B
    K -.-> G
    K -.-> F
    
    style A fill:#4caf50
    style B fill:#2196f3
    style C fill:#ff9800
    style D fill:#9c27b0
```

---

## 📋 Flowchart Usage Guide

### For README.md Integration
These flowcharts are designed to be embedded in your GitHub README to help users understand:

1. **System Architecture** - Overall system structure and components
2. **Audio Pipeline** - How voice processing works end-to-end  
3. **State Machine** - Valid state transitions and error handling
4. **WebSocket Flow** - Client-server communication protocol
5. **LLM Context** - How AI conversations are managed
6. **Error Recovery** - How the system handles failures
7. **Production Setup** - Deployment architecture considerations

### Customization Notes
- All diagrams use Mermaid syntax for GitHub compatibility
- Color coding helps distinguish component types
- Arrows show data flow and dependencies
- Subgraphs group related functionality
- Decision diamonds show branching logic

### Integration Tips
1. Add these to your main README.md file
2. Use appropriate section headers
3. Include brief explanations for each diagram
4. Link to detailed documentation for complex flows
5. Update diagrams when architecture changes

These flowcharts provide a **visual overview** that makes your sophisticated VR Interview System immediately understandable to developers, users, and contributors! 🎉

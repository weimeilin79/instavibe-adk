# Google's Agent Stack in Action:ADK, A2A, MCP on Google Cloud - InstaVibe

This repository contains the completed demo for the "Build a multi-agent system with the ADK" codelab.

## Overview

This demo showcases Google's Agent stack, ADK, MCP, and A2A with a common story to introduce agents and LLM into an existing system. This system is InstaVibe, a conceptual application that helps users, particularly those who are more introverted, connect with others and discover events. It uses a system of autonomous agents to proactively find events, manage schedules, and facilitate social interactions.

This project is the result of completing the [InstaVibe ADK Multi-Agent Codelab](https://codelabs.developers.google.com/instavibe-adk-multi-agents/instructions).

![alt Title](https://codelabs.developers.google.com/static/instavibe-adk-multi-agents/img/01-01-title_1920.png)

## Directory Structure

*   `agents/`: Houses the different agents (Planner, Social, etc.) that power the application.
*   `instavibe/`: The core Flask web application for the user-facing frontend.
*   `tools/`: Tools used by the agents.
*   `utils/`: Utility scripts.
*   `shortcut/`: Scripts for installation and removal.
*   `cloudbuild.yaml`: Configuration for Google Cloud Build.
*   `requirements.txt`: Python dependencies for the project.

## Key Architectural Elements and Technologies

![alt Architecture](https://codelabs.developers.google.com/static/instavibe-adk-multi-agents/img/02-01-architecture_1920.png)

### Google Cloud Platform (GCP)

*   **Vertex AI:**
    *   **Gemini Models:** Provides access to Google's state-of-the-art Large Language Models (LLMs) like Gemini, which power the reasoning and decision-making capabilities of our agents.
    *   **Vertex AI Agent Engine:** A managed service used to deploy, host, and scale our orchestrator agent, simplifying productionization and abstracting infrastructure complexities.
*   **Cloud Run:** A serverless platform for deploying containerized applications. We use it to:
    *   Host the main InstaVibe web application.
    *   Deploy individual A2A-enabled agents (Planner, Social Profiling, Platform Interaction) as independent microservices.
    *   Run the MCP Tool Server, making InstaVibe's internal APIs available to agents.
*   **Spanner:** A fully managed, globally distributed, and strongly consistent relational database. In this workshop, we leverage its capabilities as a Graph Database using its GRAPH DDL and query features to:
    *   Model and store complex social relationships (users, friendships, event attendance, posts).
    *   Enable efficient querying of these relationships for the Social Profiling agents.
*   **Artifact Registry:** A fully managed service for storing, managing, and securing container images.
*   **Cloud Build:** A service that executes your builds on Google Cloud. We use it to automatically build Docker container images from our agent and application source code.
*   **Cloud Storage:** Used by services like Cloud Build for storing build artifacts and by Agent Engine for its operational needs.

### Core Agent Frameworks & Protocols

*   **Google's Agent Development Kit (ADK):** The primary framework for:
    *   Defining the core logic, behavior, and instruction sets for individual intelligent agents.
    *   Managing agent lifecycles, state, and memory (short-term session state and potentially long-term knowledge).
    *   Integrating tools (like Google Search or custom-built tools) that agents can use to interact with the world.
    *   Orchestrating multi-agent workflows, including sequential, loop, and parallel execution of sub-agents.
*   **Agent-to-Agent (A2A) Communication Protocol:** An open standard enabling:
    *   Direct, standardized communication and collaboration between different AI agents, even if they are running as separate services or on different machines.
    *   Agents to discover each other's capabilities (via Agent Cards) and delegate tasks. This is crucial for our Orchestrator agent to interact with the specialized Planner, Social, and Platform agents.
*   **A2A Python Library (a2a-python):** The concrete library used to make our ADK agents speak the A2A protocol. It provides the server-side components needed to:
    *   Expose our agents as A2A-compliant servers.
    *   Automatically handle serving the "Agent Card" for discovery.
    *   Receive and manage incoming task requests from other agents (like the Orchestrator).
*   **Model Context Protocol (MCP):** An open standard that allows agents to:
    *   Connect with and utilize external tools, data sources, and systems in a standardized way.
    *   Our Platform Interaction Agent uses an MCP client to communicate with an MCP server, which in turn exposes tools to interact with the InstaVibe platform's existing APIs.

### Debugging Tools

*   **A2A Inspector:** The A2A Inspector is a web-based debugging tool used throughout this workshop to connect to, inspect, and interact with our A2A-enabled agents. While not part of the final production architecture, it is an essential part of our development workflow. It provides:
    *   **Agent Card Viewer:** To fetch and validate an agent's public capabilities.
    *   **Live Chat Interface:** To send messages directly to a deployed agent for immediate testing.
    *   **Debug Console:** To view the raw JSON-RPC messages being exchanged between the inspector and the agent.

### Language Models (LLMs): The "Brains" of the System

*   **Google's Gemini Models:** Specifically, we utilize versions like gemini-2.0-flash. These models are chosen for:
    *   **Advanced Reasoning & Instruction Following:** Their ability to understand complex prompts, follow detailed instructions, and reason about tasks makes them suitable for powering agent decision-making.
    *   **Tool Use (Function Calling):** Gemini models excel at determining when and how to use the tools provided via ADK, enabling agents to gather information or perform actions.
    *   **Efficiency (Flash Models):** The "flash" variants offer a good balance of performance and cost-effectiveness, suitable for many interactive agent tasks that require quick responses.

## Getting Started

### Prerequisites

*   A clean Google Cloud Project with billing enabled. It is recommended to use a project with no organization-level policies applied, as they may interfere with the deployment of resources. Proceed at your own risk if using a project with existing policies.

### Installation

The following steps should be run in Google Cloud Shell.

1.  Clone the repository:
    ```bash
    git clone https://github.com/weimeilin79/instavibe-adk.git
    ```
2.  Navigate to the `shortcut` directory and run the installation script:
    ```bash
    cd instavibe-adk/shortcut
    chmod +x *.sh
    ./install_all.sh
    ```

### Running the Application

Please refer to the codelab for detailed instructions on running the different components.


### Remove/Uninstall

1.  Navigate to the `shortcut` directory and run the removal script:
    ```bash
    cd instavibe-adk/shortcut
    ./remove.sh
    ```



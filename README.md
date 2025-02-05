# Personal Offline Chatbot

This repository provides the setup and instructions to run the Personal Offline Chatbot using the `deepseek-r1:1.5b` model.

## Steps to Setup

### 1. Download Ollama Setup

- First, download the Ollama setup link to get started.
-  ```bash
    link:  https://ollama.com/
    ```

### 2. Download the Model

- Run the following command to download the `deepseek-r1:1.5b` model:

    ```bash
    ollama run deepseek-r1:1.5b
    ```

### 3. Start the Ollama Server

- To start the Ollama server, use the following command:

    ```bash
    ollama run
    ```

### 4. Clone This Repository

- Clone the repository to your local machine:

    ```bash
    git clone https://github.com/mutti-dev/Personal-offline-chatbot.git
    ```

### 5. Create a Virtual Environment

- Create a virtual environment using the following command:

    ```bash
    python -m venv venv
    ```

### 6. Install Required Packages

- Install the required packages by running:

    ```bash
    pip install -r requirements.txt
    ```

### 7. Run the Application

- Once the packages are installed, run the `app.py` file:

    ```bash
    python app.py
    ```




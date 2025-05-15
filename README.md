# Team Project - Summer 25: Real-time Virtual Meeting Assistant
![Header](./header.png)

## 🌟 About the Project

Welcome to the **Real-time Virtual Meeting Assistant**! Our goal is to revolutionize virtual meeting applications by enabling real-time interactions based on meeting context and user-specific knowledge. Imagine you're attending an online lecture and a complex concept you're unfamiliar with is mentioned – our assistant will instantly provide a concise, understandable explanation, allowing you to follow the rest of the session seamlessly.

# Access project board via Miro
URL[https://miro.com/welcomeonboard/YnFMWXpjUjdaelJ3Q2pNb0lTVTczelRwTWUvUk9YTHNqOUtWZzdBM2lDa1VjZWZiNnNFSWtqMXRKS2xQd3pNa3VxQ25oTTBad2JLd2pJME5UTVRoeVVPRFZFWVF1dEpQcGJJbTFJa0R1ckRWaDlEZU1VQ0ZmdjFicndBazV5NHZhWWluRVAxeXRuUUgwWDl3Mk1qRGVRPT0hdjE=?share_link_id=674549526661]

This project originated from the idea of explaining complex concepts in real-time during virtual meetings and has since expanded to include a variety of dynamic content. This includes:

* **Real-time Explanations:** Instant clarification of jargon or complex topics.
* **Live Bullet-Point Summaries:** Automatic generation of meeting highlights.
* **Conversation Backtracing:** Easily follow discussion threads.
* **Ideation Suggestions:** AI-powered prompts based on the conversation flow.

We leverage the power of modern Large Language Models (`LLMs`) and multi-modal models to realize these functionalities – features not yet fully supported even by leading platforms like Zoom AI. The key to all of this is **real-time capability**.

## 🚀 Implementation Approach

Our planned pipeline is as follows:

1.  **Access to Meeting Data:** Capture audio (and optionally screen) content from the virtual meeting application (specifically Google Meet).
2.  **Speech-to-Text (`STT`):**
    * For each participant's audio stream in the call, apply `STT` to audio segments.
    * Split the transcribed text at sentence endings (e.g., ".", "!", "?").
3.  **`LLM` Processing & Feature Generation:**
    * Evaluate each sentence for domain-specific technical terms.
    * For each detected technical term, send the sentence, the detected term, and relevant knowledge about other participants' backgrounds to the text inference model (`LLM`).
    * A system prompt will guide the `LLM` to explain the term contextually.
4.  **Content Display:**
    * Send the `LLM`'s response (e.g., the explanation) to the Google Meet plugin.
    * Display the information as a pop-up or appropriate in-app notification.

## 🛠️ Project Groups

To implement this ambitious project, we have formed three specialized groups:

1.  **App Group:** Responsible for the integration with **Google Meet**. This includes developing a plugin/extension to access meeting content (audio streams) and to display the generated information (e.g., pop-ups with explanations) within the Google Meet interface.

2.  **`STT` Group:** Focuses on the implementation and optimization of speech-to-text conversion from the Google Meet audio streams.
    * **Technology:** Use of existing models, e.g., via [Hugging Face SpeechToText](https://huggingface.co/docs/transformers/en/model_doc/speech_to_text).

3.  **`LLM` Group:** Responsible for processing the transcribed text to identify technical terms and generate explanations or other desired outputs using `LLMs`. This includes crafting effective prompts and potentially fine-tuning models.
    * **Possible Models:** Qwen 2.5-VL ([QwenLM/Qwen2.5-VL](https://github.com/QwenLM/Qwen2.5-VL)), Qwen 3 ([QwenLM/Qwen3](https://github.com/QwenLM/Qwen3)), or other models via frameworks like Hugging Face.

## 💻 Development Environment (Optional)

For computationally intensive tasks, especially `LLM` experiments, a workstation with an NVIDIA 3090 (24GB VRAM) is available. Access is via `SSH`. Team members will receive access credentials after submitting their public `SSH` key.


### 1. App Group (Frontend - Google Meet Integration)

This group focuses on the interface and interaction within Google Meet, acting as the bridge between the user and the backend processing.

* **Google Meet Integration:**
    * Research and understand the capabilities and limitations of Google Meet extension/plugin APIs.
    * Design and develop the architecture for a Google Meet browser extension or plugin.
    * Implement functionality to access and capture audio streams from all meeting participants.
    * (Optional) Implement functionality to capture screen content if deemed necessary for certain features (e.g., visual context).
* **Data Handling:**
    * Develop methods to reliably send captured audio data (or transcribed text, depending on the pipeline design) to the backend (likely the STT group initially).
    * Implement mechanisms to receive processed information (like explanations, summaries, etc.) from the backend (from the LLM group).
* **User Interface (UI):**
    * Design and implement UI elements within the Google Meet interface to display the AI-generated information. This could involve pop-ups, sidebars, notifications, or overlays.
    * Ensure the UI is non-intrusive and user-friendly during a live meeting.
* **Communication Layer:**
    * Establish a robust communication channel (e.g., WebSockets, HTTP requests) between the browser extension and your backend services.

### 2. STT Group (Speech-to-Text Processing)

This group is responsible for converting the raw audio from the meeting into accurate, structured text that the LLM group can process.

* **Model Selection & Setup:**
    * Research and select suitable Speech-to-Text models, prioritizing real-time performance and accuracy for conversational speech (e.g., exploring options on Hugging Face).
    * Set up the necessary environment for running the chosen STT model(s), potentially leveraging the available GPU workstation.
* **Audio Processing:**
    * Develop code to receive audio data streams or chunks from the App group.
    * Implement the STT inference process to transcribe the audio into text.
    * Handle potential challenges like overlapping speech, background noise, and variations in speaker volume/accent.
* **Text Structuring:**
    * Implement logic to split the continuous transcription into individual sentences based on punctuation marks ('.', '!', '?').
    * Ensure accurate segmentation to provide meaningful units of text to the LLM.
* **Output & Integration:**
    * Develop an API endpoint or communication method to send the transcribed and sentence-split text to the LLM group for further processing.
    * Manage the processing of multiple participant audio streams simultaneously and associate the text with the correct speaker.

### 3. LLM Group (Backend - Processing & Inference)

This group forms the core intelligence of the project, processing the text, identifying key information, and generating relevant outputs using Large Language Models.

* **Model Selection & Setup:**
    * Research and select appropriate Large Language Models (LLMs) based on their capabilities for tasks like term identification, explanation, summarization, etc. (e.g., exploring Qwen variants, other models on Hugging Face).
    * Set up the inference environment for the selected LLM(s), making effective use of the available GPU resources (NVIDIA 3090).
* **Text Analysis:**
    * Develop code to receive the transcribed and sentence-split text from the STT group.
    * Implement logic or use LLM capabilities to identify domain-specific technical terms or concepts within the text.
    * Potentially integrate external knowledge bases or participant-specific knowledge if the project aims for personalized explanations.
* **Prompt Engineering & Inference:**
    * Design effective system and user prompts for the LLM to generate desired outputs (e.g., clear and concise explanations of technical terms in context).
    * Implement the calling and handling of the LLM inference process.
* **Feature Generation:**
    * Develop the logic to generate the specific outputs requested by the project, such as:
        * Contextual explanations for identified terms.
        * Real-time bullet-point summaries.
        * Conversation backtracing points.
        * Ideation suggestions.
* **Output & Integration:**
    * Develop an API endpoint or communication method to send the generated outputs (e.g., the explanation text) back to the App group for display in Google Meet.
    * Manage the orchestration of the pipeline: receiving from STT, processing, and sending to the App group.

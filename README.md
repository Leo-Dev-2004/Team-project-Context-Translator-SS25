# Team Project - Summer 25: Real-time Virtual Meeting Assistant

## 🌟 About the Project

Welcome to the **Real-time Virtual Meeting Assistant**! Our goal is to revolutionize virtual meeting applications by enabling real-time interactions based on meeting context and user-specific knowledge. Imagine you're attending an online lecture and a complex concept you're unfamiliar with is mentioned – our assistant will instantly provide a concise, understandable explanation, allowing you to follow the rest of the session seamlessly.

This project originated from the idea of explaining complex concepts in real-time during virtual meetings and has since expanded to include a variety of dynamic content. This includes:

* **Real-time Explanations:** Instant clarification of jargon or complex topics.
* **Live Bullet-Point Summaries:** Automatic generation of meeting highlights.
* **Conversation Backtracing:** Easily follow discussion threads.
* **Ideation Suggestions:** AI-powered prompts based on the conversation flow.

We leverage the power of modern Large Language Models (`LLMs`) and multi-modal models to realize these functionalities – features not yet fully supported even by leading platforms like Zoom AI. The key to all of this is **real-time capability**.

## 🚀 Implementation Approach

Our planned pipeline is as follows:

1.  **Access to Meeting Data:** Capture audio (and optionally screen) content from the virtual meeting application.
2.  **Speech-to-Text (`STT`):** Transcribe audio into text using current `STT` models (e.g., via [Hugging Face Transformers](https://huggingface.co/docs/transformers/en/model_doc/speech_to_text)).
3.  **`LLM` Processing:** Utilize `LLMs` to analyze transcripts and extract or generate the desired information. User-specific backgrounds (e.g., "Bachelor's student in Computer Science") can be considered here to optimize the relevance of the results.
4.  **Content Display:** Generate and display teaser graphics and texts directly within the meeting application.

## 🛠️ Project Groups

To implement this ambitious project, we have formed three specialized groups:

1.  **App Group:** Responsible for integration with virtual meeting apps. This includes accessing meeting content and displaying the generated information.
    * **Possible Approaches:** Developing an extension for existing apps (e.g., Google Meet, Zoom) or direct development based on open-source platforms like [Jitsi Meet](https://github.com/jitsi/jitsi-meet).
    * **Interested:** Leon, Luiz, Hannah, Konstantin

2.  **`STT` Group:** Focuses on the implementation and optimization of speech-to-text conversion.
    * **Technology:** Use of existing models, e.g., via [Hugging Face SpeechToText](https://huggingface.co/docs/transformers/en/model_doc/speech_to_text).
    * **Interested:** Luiz, Ziyue, Yihua, Leo, Konstantinos

3.  **`LLM` Group:** Responsible for "translating" transcripts into the desired features (explanations, summaries, etc.).
    * **Possible Models:** Qwen 2.5-VL ([QwenLM/Qwen2.5-VL](https://github.com/QwenLM/Qwen2.5-VL)), Qwen 3 ([QwenLM/Qwen3](https://github.com/QwenLM/Qwen3)), or other models via frameworks like Hugging Face.
    * **Interested:** Andrew, Ziyue, Hannah, Leo, Konstantinos

## 💻 Development Environment (Optional)

For computationally intensive tasks, especially `LLM` experiments, a workstation with an NVIDIA 3090 (24GB VRAM) is available. Access is via `SSH`. Team members will receive access credentials after submitting their public `SSH` key.

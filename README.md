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
    * **Interested:** Leon, Luiz, Hannah, Konstantin

2.  **`STT` Group:** Focuses on the implementation and optimization of speech-to-text conversion from the Google Meet audio streams.
    * **Technology:** Use of existing models, e.g., via [Hugging Face SpeechToText](https://huggingface.co/docs/transformers/en/model_doc/speech_to_text).
    * **Interested:** Luiz, Ziyue, Yihua, Leo, Konstantinos

3.  **`LLM` Group:** Responsible for processing the transcribed text to identify technical terms and generate explanations or other desired outputs using `LLMs`. This includes crafting effective prompts and potentially fine-tuning models.
    * **Possible Models:** Qwen 2.5-VL ([QwenLM/Qwen2.5-VL](https://github.com/QwenLM/Qwen2.5-VL)), Qwen 3 ([QwenLM/Qwen3](https://github.com/QwenLM/Qwen3)), or other models via frameworks like Hugging Face.
    * **Interested:** Andrew, Ziyue, Hannah, Leo, Konstantinos

## 💻 Development Environment (Optional)

For computationally intensive tasks, especially `LLM` experiments, a workstation with an NVIDIA 3090 (24GB VRAM) is available. Access is via `SSH`. Team members will receive access credentials after submitting their public `SSH` key.

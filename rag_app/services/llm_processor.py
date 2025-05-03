from langchain.llm import LlamaModel

class LLMProcessor:
    def __init__(self):
        self.model = LlamaModel(model_name="llama")

    def summarize(self, text):
        return self.model.summarize(text)

    def explain(self, text):
        return self.model.explain(text)

    def query(self, question, text):
        return self.model.answer(question, context=text)

from backend.services.llm_service import LLMService

res, err = LLMService._try_parse('Here is the json:\n```json\n{"score": 8}\n```\nHope this helps!')
print(res)

res2, err2 = LLMService._try_parse('{"score": 8} Some extra string }')
print(res2)

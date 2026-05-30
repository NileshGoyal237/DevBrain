
import asyncio
from services.llm_service import llm

async def main():
    try:
        res = await llm.call('Hello')
        print(f'SUCCESS: {res}')
    except Exception as e:
        print(f'ERROR: {type(e)} {e}')

asyncio.run(main())


from fastapi import FastAPI
from app.function_definitions import functions
from app.functions import api_functions, create_pizzas
from app.handler import OpenAIHandler
from app.models import Conversation
from app.db import Base, engine, Session, Review, Order
from app.prompts import system_message, hiring_prompt_template
from app.store import create_store
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import re
import logging
import redis
from collections.abc import Generator
from typing import Any, Dict, List
import openai
from fastapi.responses import StreamingResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

handler = OpenAIHandler(api_functions, functions, system_message)
R = redis.Redis(host="redis", port=6379, db=0)


@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    create_pizzas()
    # if not os.path.exists("vectorstore.pkl"):
    #     create_store()


@app.on_event("shutdown")
async def shutdown_event():
    os.remove("pizzadb.db")


@app.post("/restaurant/conversation/{conversation_id}")
async def query_endpoint(conversation_id: str, conversation: Conversation):
    logger.info(f"Sending Conversation with ID {conversation_id} to OpenAI")
    existing_conversation_json = R.get(conversation_id)
    if existing_conversation_json:
        existing_conversation = json.loads(existing_conversation_json)
    else:
        existing_conversation = {
            "conversation": [
                {"role": "assistant", "content": "You are a helpful assistant."}
            ]
        }
    if conversation.dict()["lastResponse"]:
        existing_conversation["conversation"].append(
            {"role": "assistant", "content": conversation.dict()["lastResponse"]}
        )
    # existing_conversation["conversation"].append({"role": "user", "content": conversation.dict()["conversation"][-1]})
    # If user interrupted then remove the last assistant response
    if conversation.dict()["interruption"]:
        for i in range(len(existing_conversation["conversation"]) - 1, -1, -1):
            if existing_conversation["conversation"][i]["role"] == "assistant":
                del existing_conversation["conversation"][i]
                break
    # Append the new message from the conversation
    new_message = conversation.dict()["conversation"][-1]
    existing_conversation["conversation"].append(new_message)
    print(existing_conversation["conversation"])
    R.set(conversation_id, json.dumps(existing_conversation))
    model_id = "ft:gpt-3.5-turbo-0125:personal::9Ctr9YCw"

    # response = get_response(existing_conversation["conversation"])
    async def generate_response():
        for content in get_response(
            existing_conversation["conversation"], system_message, model_id
        ):
            yield content  # Assuming get_response returns strings

    return StreamingResponse(generate_response(), media_type="text/event-stream")


@app.get("/reviews")
async def get_all_reviews():
    session = Session()
    reviews = session.query(Review).all()
    session.close()
    return reviews


@app.get("/orders")
async def get_all_orders():
    session = Session()
    orders = session.query(Order).all()
    session.close()
    return orders


@app.post("/recruitment/conversation/{conversation_id}")
async def hiring_endpoint(conversation_id: str, conversation: Conversation):
    logger.info(f"Sending Conversation with ID {conversation_id} to OpenAI")
    existing_conversation_json = R.get(conversation_id)
    if existing_conversation_json:
        existing_conversation = json.loads(existing_conversation_json)
    else:
        existing_conversation = {
            "conversation": [
                {
                    "role": "assistant",
                    "content": "Hello, this is Echo from Echo Sense. I hope you're doing well today. I came across your profile and found it quite interesting. Are you currently considering a job change?",
                }
            ]
        }
    if conversation.dict()["lastResponse"]:
        existing_conversation["conversation"].append(
            {"role": "assistant", "content": conversation.dict()["lastResponse"]}
        )
    # existing_conversation["conversation"].append({"role": "user", "content": conversation.dict()["conversation"][-1]})
    # If user interrupted then remove the last assistant response
    if conversation.dict()["interruption"]:
        for i in range(len(existing_conversation["conversation"]) - 1, -1, -1):
            if existing_conversation["conversation"][i]["role"] == "assistant":
                del existing_conversation["conversation"][i]
                break
    # Append the new message from the conversation
    new_message = conversation.dict()["conversation"][-1]
    existing_conversation["conversation"].append(new_message)
    print(existing_conversation["conversation"])
    R.set(conversation_id, json.dumps(existing_conversation))
    model_id = "ft:gpt-3.5-turbo-0125:personal::9GpWUW63"

    # response = get_response(existing_conversation["conversation"])
    async def generate_response():
        inside_json, full_response = False, []
        try:
            for content in get_response(
                existing_conversation["conversation"], hiring_prompt_template, model_id
            ):
                full_response.append(content)
                if "{" in content:
                    inside_json = True
                    idx = content.index("{")
                    yield content[:idx] + content[idx + 1 :]
                    continue
                elif "}" in content:
                    inside_json = False
                    idx = content.index("}")
                    yield content[:idx] + content[idx + 1 :]
                    continue
                if inside_json:
                    continue

                yield content  # Assuming get_response returns strings
        finally:
            full_response = "".join(full_response)
            json_response = re.findall(r"\{[\s\S]*\}", full_response)
            if json_response:
                R.set(f"{conversation_id}_json", json_response[0])

    return StreamingResponse(generate_response(), media_type="text/event-stream")


@app.post("/recruitment/conversation_json/{conversation_id}")
async def get_conversation_result(conversation_id: str):
    return R.get(f"{conversation_id}_json")


def call_function(function_name: str, function_arguments: str) -> str:
    """Calls a function and returns the result."""

    # Ensure the function is defined
    if function_name not in api_functions:
        return "Function not defined."

    # Convert the function arguments from a string to a dict
    function_arguments_dict = json.loads(function_arguments)
    print("function_name")
    print(function_name)
    print(function_arguments)
    func = api_functions[function_name]
    print(func(**function_arguments_dict))
    # print(api_functions[function_name]["parameters"])
    # Ensure the function arguments are valid
    # function_parameters = api_functions[function_name]["parameters"]["properties"]
    # for argument in function_arguments_dict:
    #     if argument not in function_parameters:
    #         return f"{argument} not defined."

    # Call the function and return the result
    return func(**function_arguments_dict)


def get_response(
    query_messages: List[Dict[str, Any]], prompt_template, model_id: str
) -> Generator[str, None, None]:
    default_messages = [
        {
            "role": "system",
            "content": prompt_template,
        },
    ]
    default_messages.extend(query_messages)
    response = openai.ChatCompletion.create(
        # model="gpt-3.5-turbo-0613",
        model=model_id,
        messages=default_messages,
        functions=functions,
        stream=True,
    )

    # Define variables to hold the streaming content and function call
    streaming_content = ""
    function_call = {"name": "", "arguments": ""}

    # Loop through the response chunks
    for chunk in response:
        # Handle errors
        if not "choices" in chunk:
            messages.append(
                {
                    "role": "assistant",
                    "content": "Sorry, there was an error. Please try again.",
                }
            )
            yield "Sorry, there was an error. Please try again."
            break

        # Get the first choice
        msg = chunk["choices"][0]

        # If there's still more to output...
        if "delta" in msg:
            # If it's a function call, save it for later
            if "function_call" in msg["delta"]:
                if "name" in msg["delta"]["function_call"]:
                    function_call["name"] += msg["delta"]["function_call"]["name"]
                if "arguments" in msg["delta"]["function_call"]:
                    function_call["arguments"] += msg["delta"]["function_call"][
                        "arguments"
                    ]

            # If it's content, add it to the streaming content and yield it
            elif "content" in msg["delta"]:
                streaming_content += msg["delta"]["content"]
                yield msg["delta"]["content"]

        # If it's the end of the response and it's a text response, update the messages array with it
        if msg["finish_reason"] == "stop":
            default_messages.append({"role": "assistant", "content": streaming_content})

        # If it's the end of the response and it's a function call, call the function, update the messages array
        # and recursively call get_response() so GPT can respond to the function call output
        elif msg["finish_reason"] == "function_call":
            function_output = call_function(
                function_call["name"], function_call["arguments"]
            )
            default_messages.append(
                {
                    "role": "function",
                    "content": function_output,
                    "name": function_call["name"],
                }
            )
            yield from get_response(default_messages)

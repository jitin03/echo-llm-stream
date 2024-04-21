import json
import os

import openai
from dotenv import find_dotenv, load_dotenv


class OpenAIHandler:
    def __init__(
        self,
        api_functions,
        function_definitions,
        system_message,
        model="gpt-3.5-turbo-0613",
    ):
        load_dotenv(find_dotenv())
        openai.api_key = os.environ.get("OPENAI_API_KEY")
        if openai.api_key is None:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

        self.api_functions = api_functions
        self.function_definitions = function_definitions
        self.model = model
        self.system_message = system_message
    def call_function(self,function_name: str, function_arguments: str) -> str:
        """Calls a function and returns the result."""

        # Ensure the function is defined
        if function_name not in FUNCTIONS:
            return "Function not defined."

        # Convert the function arguments from a string to a dict
        function_arguments_dict = json.loads(function_arguments)

        # Ensure the function arguments are valid
        function_parameters = FUNCTIONS[function_name]["parameters"]["properties"]
        for argument in function_arguments_dict:
            if argument not in function_parameters:
                return f"{argument} not defined."

        # Call the function and return the result
        return globals()[function_name](**function_arguments_dict)
    def send_message(self, query_messages):
        default_messages=[
                {
                    "role": "system",
                    "content": self.system_message,
                },
               
            ]
        default_messages.extend(query_messages)
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=default_messages,
            functions=self.function_definitions,
            stream=true
        )
        # message = response["choices"][0]["message"]



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
                yield from get_response(
                                default_messages
                            )
                
                # second_response = openai.ChatCompletion.create(
                #                                     model=self.model,
                #                                     messages=default_messages,
                #                                     stream=true
                #                                 )
                # for chunk in second_response:
                #     msg = chunk["choices"][0]








        
  
    def process_function_call(self, message):
        if message.get("function_call"):
            print(message.get("function_call"))
            function_name = message["function_call"]["name"]
            function_args_json = message["function_call"].get("arguments", {})
            function_args = json.loads(function_args_json)

            api_function = self.api_functions.get(function_name)

            if api_function:
                result = str(api_function(**function_args))
                return function_name, result
            else:
                print(f"Function {function_name} not found")
        return None, None

    def send_response(self, query):
        message = self.send_message(query)
        function_name, result = self.process_function_call(message)

        if function_name and result:
            print("Function call necessary to fulfill users request")
            second_response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_message,
                    },
                    {"role": "user", "content": query},
                    message,
                    {
                        "role": "function",
                        "name": function_name,
                        "content": result,
                    },
                ],
            )
            return second_response["choices"][0]["message"]["content"]
        else:
            return message["content"]

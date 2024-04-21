import json
import os
from openai import OpenAI
import openai
from dotenv import find_dotenv, load_dotenv
client = OpenAI(api_key = "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")
ROLE_CLASS_MAP = {
    "assistant": "assistant",
    "user": "user",
    "system": "system"
}
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

    def send_message(self, default_messages):
    
        response = client.chat.completions.create(
            model=self.model,
            messages = default_messages,
            functions=self.function_definitions,
         
        )
       
        message = response.choices[0].message
        return message
    def create_messages(self,conversation):
        return [ROLE_CLASS_MAP[message.role](content=message.content) for message in conversation]




    def process_function_call(self, message):
        
        if message.function_call:
            print(message.function_call)
            function_name = message.function_call.name
            function_args_json = message.function_call.arguments
            function_args = json.loads(function_args_json)

            api_function = self.api_functions.get(function_name)

            if api_function:
                result = str(api_function(**function_args))
                return function_name, result
            else:
                print(f"Function {function_name} not found")
        return None, None

    def send_response(self, query_messages):

        default_messages=[{
                    "role": "system",
                    "content": self.system_message,
                }]
        default_messages.extend(query_messages)

        print(default_messages)
        message = self.send_message(default_messages)
        function_name, result = self.process_function_call(message)
       
        if function_name and result:
            print("Function call necessary to fulfill users request")
            
            temp =[
            
                    message,
                    {
                        "role": "function",
                        "name": function_name,
                        "content": result,
                    },
                ]
            default_messages.extend(temp)
            second_response = client.chat.completions.create(
                model=self.model,
                messages=default_messages,
                
            )
            return second_response.choices[0].message.content
        else:
            return message.content

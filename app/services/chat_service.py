from app.chains.travel_chain import travel_chain

class ChatService:
    def generate_response(
            self,
            message:str,
    )->str:
        response=travel_chain.invoke(
            {
                "user_input":message
           }
        )
        return response
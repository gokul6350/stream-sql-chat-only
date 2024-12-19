import streamlit as st
import sqlite3
import google.generativeai as genai
from threading import Lock

def remove_sql_markers(text):
    if text.startswith("```sql"):
        text = text.replace("```sql", "")
        text = text.replace("\n```", "")
        return text.strip()
    else:
        return text

class HospitalDatabaseQA:
    def __init__(self, db_path="instance/hospital.db"):
        self.db_path = db_path
        self.lock = Lock()
        # Setup Gemini for each request
        genai.configure(api_key="AIzaSyBoUqeC-oQDQQWMe5-Vcmd17RoGw8qqZVM")
        
        # Get schema during initialization
        schema = self._get_database_schema()
        
        self.sql_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            },
            system_instruction=f"""Given the following SQLite database schema:
{schema}

You are a SQL query generator. When given a question, generate ONLY the SQL query needed to answer it, without any explanations.
If no answer can be found, return "SELECT 0 WHERE 0;".
Keep responses focused and precise, returning only valid SQL queries."""
        )
        
        # Create two separate models with their own configurations
        self.format_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
        )
        
        # Initialize both chats with their respective histories
        if 'history_toggle' in st.session_state and st.session_state.history_toggle:
            # SQL Chat initialization
            chat_history = []
            for entry in st.session_state.sql_history:
                chat_history.extend([
                    {"role": "user", "parts": [entry["prompt"]]},
                    {"role": "model", "parts": [entry["query"]]}
                ])
            self.sql_chat = self.sql_model.start_chat(history=chat_history)
            
            # Format Chat initialization
            format_chat_history = []
            for entry in st.session_state.format_history:
                format_chat_history.extend([
                    {"role": "user", "parts": [entry["prompt"]]},
                    {"role": "model", "parts": [entry["result"]]}
                ])
            self.format_chat = self.format_model.start_chat(history=format_chat_history)
        else:
            self.sql_chat = self.sql_model.start_chat(history=[])
            self.format_chat = self.format_model.start_chat(history=[])
        

    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
        
    def _get_database_schema(self):
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            schema = []
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                schema.append(f"Table {table_name}:")
                for col in columns:
                    schema.append(f"  - {col[1]} ({col[2]})")
            
            conn.close()
            return "\n".join(schema)

    def ask(self, question):
        try:
            print("\n========== PROCESSING NEW QUERY ==========")
            print(f"User Input: {question}")
            
            # 1. Get database schema
            schema = self._get_database_schema()
            
            # 2. Generate SQL query from user question using chat history
            sql_prompt = f"""question: {question}"""
            
            print("\n---------- SQL Prompt ----------")
            print(sql_prompt)
            
            # Use chat with history instead of single generate_content
            sql_response = self.sql_chat.send_message(sql_prompt)
            sql_query = remove_sql_markers(sql_response.text.strip())
            
            # Update session state history with the chat history
            st.session_state.sql_history = [
                {"role": msg.role, "parts": [part.text for part in msg.parts]}
                for msg in self.sql_chat.history
            ]
            
            print("\n---------- Generated SQL Query ----------")
            print(sql_query)
            
            # Store SQL prompt in history
       
            st.session_state.sql_history.append({
                    "prompt": sql_prompt,
                    "query": sql_query
                })
            
            # 3. Execute query and get results
            print("\n---------- Executing Query ----------")
            try:
                with self.lock:
                    conn = self.get_connection()
                    cursor = conn.cursor()
                    is_select = sql_query.strip().upper().startswith('SELECT')
                    cursor.execute(sql_query)
                    
                    if is_select:
                        results = cursor.fetchall()
                        column_names = [description[0] for description in cursor.description]
                        formatted_results = []
                        for row in results:
                            formatted_row = dict(zip(column_names, row))
                            formatted_results.append(formatted_row)
                        print(f"formatted_results: {formatted_results}")
                        data_message = f"Query returned: {formatted_results[:11]}"
                    else:
                        conn.commit()
                        affected_rows = cursor.rowcount
                        data_message = f"Operation successful. Affected rows: {affected_rows}"
                    
                    conn.close()
            except Exception as e:
                data_message = f"Error executing query: {str(e)}"
                print(f"\n---------- SQL Error ----------")
                print(data_message)
            
            print("\n---------- Query Results ----------")
            print(data_message)

            # 4. Format final response
            format_prompt = f"""
            Question: {question}
            SQL Query: {sql_query}
            Result: {data_message}
            
            Please provide a natural, helpful response about results of what was done.
            """
            
            print("\n---------- Format Prompt ----------")
            print(format_prompt)
            
            st.session_state.format_history.append({
                    "prompt": format_prompt,
                    "result": data_message
                })            
            # Use format chat instead of generate_content
            final_response = self.format_chat.send_message(format_prompt)
            
            # Update format history in session state
            st.session_state.format_history = [
                {"role": msg.role, "parts": [part.text for part in msg.parts]}
                for msg in self.format_chat.history
            ]
            
            print("\n---------- Final Response ----------")
            print(final_response.text.strip())
            print("\n====================================")
            
            return final_response.text.strip()
            
        except Exception as e:
            print(f"\n---------- ERROR ----------")
            print(f"Error occurred: {str(e)}")
            print("\n====================================")
            return f"Error: {e}"

def chat_interface():
    # Initialize qa_system and histories in session state
    if "qa_system" not in st.session_state:
        st.session_state.qa_system = HospitalDatabaseQA()
        print(f"qa_system initialized")
    if "sql_history" not in st.session_state:
        st.session_state.sql_history = []
        print(f"sql_history reseted")
    if "format_history" not in st.session_state:
        st.session_state.format_history = []
        print(f"format_history reseted")
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        print(f"chat_messages reseted")
    # Initialize history_toggle if it doesn't exist
    if "history_toggle" not in st.session_state:
        st.session_state.history_toggle = False
        print(f"history_toggle initialized")

    # Add buttons to sidebar
    with st.sidebar:
        if st.button("Reset All History"):
            st.session_state.chat_messages = []
            st.session_state.sql_history = []
            st.session_state.format_history = []
            st.rerun()
            
        # Initialize toggle state in session if it doesn't exist
        if 'history_toggle' not in st.session_state:
            st.session_state.history_toggle = False
            
        # Add toggle that does nothing
        st.toggle('🔄 Chat Memory', key='history_toggle')

    # Display chat messages in main screen
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

        # Chat input
    if prompt := st.chat_input("Ask about the database..."):
            # Add user message to chat history
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            

             # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate and display assistant response
            with st.chat_message("assistant"):
                with st.status("Processing query...", expanded=True) as status:
                    st.write("Generating SQL query...")
                    response = st.session_state.qa_system.ask(prompt)
                    # Display the SQL query from history
                    if st.session_state.sql_history:
                        latest_query = st.session_state.sql_history[-1]['query']
                        st.write(latest_query)
                        print(f"latest_query: {latest_query}")
                    else:
                        print(f"st.session_state.sql_history: {st.session_state.sql_history}")  
                        print(f"chat_messages: {st.session_state.chat_messages}")  

                    st.write("Executing database query...")
                    status.update(label="Complete!", state="complete",expanded=False)
                st.markdown(response)
                
            # Add assistant response to chat history
            st.session_state.chat_messages.append({"role": "assistant", "content": response})
            print(f"sql_history: {st.session_state.sql_history}")

def main():
    st.title("Chat with SQL Database")
    chat_interface()

if __name__ == "__main__":
    main()

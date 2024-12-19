import streamlit as st
import sqlite3
import pandas as pd

def init_db():
    try:
        conn = sqlite3.connect('instance/hospital.db', check_same_thread=False)
        c = conn.cursor()
        return conn, c
    except sqlite3.Error as e:
        st.error(f"Database connection error: {e}")
        return None, None

def get_all_tables():
    conn, c = init_db()
    if conn and c:
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = c.fetchall()
        return [table[0] for table in tables]
    return []

def _get_database_schema():
    conn, c = init_db()
    if conn and c:
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = c.fetchall()
        
        schema = []
        for table in tables:
            table_name = table[0]
            schema.append("\n" + "="*50)
            schema.append(f"Table: {table_name}")
            schema.append("="*50)
            
            c.execute(f"PRAGMA table_info({table_name});")
            columns = c.fetchall()
            
            schema.append(f"{'Column Name':<20} {'Type':<15} {'Not Null':<10} {'Default':<15} {'Primary Key'}")
            schema.append("-"*70)
            
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                not_null = "Yes" if col[3] else "No"
                default_val = str(col[4]) if col[4] is not None else ""
                primary_key = "Yes" if col[5] else "No"
                
                schema.append(f"{col_name:<20} {col_type:<15} {not_null:<10} {default_val:<15} {primary_key}")
        
        return "\n".join(schema)
    return "No schema available."

def view_database():
    tables = get_all_tables()
    if tables:
        selected_table = st.selectbox("Select Table", tables)
        if selected_table:
            conn, c = init_db()
            if conn and c:
                df = pd.read_sql_query(f"SELECT * FROM {selected_table}", conn)
                st.dataframe(df)
    else:
        st.warning("No tables found in database")

def view_table_structure():
    schema = _get_database_schema()
    st.text(schema)  # Using st.text for fixed-width font

def main():
    st.set_page_config(layout="wide")
    st.title("Database Viewer")
    
    # Create two tabs for different views
    tab1, tab2 = st.tabs(["View Database", "Table Structure"])
    
    with tab1:
        view_database()
    
    with tab2:
        view_table_structure()

if __name__ == "__main__":
    main()

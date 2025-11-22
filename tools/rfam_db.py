import mysql.connector

def execute_sql_query(query: str) -> str:
    """
    Execute a SQL query against the Rfam public database.
    
    Args:
        query: The SQL query to execute.
        
    Returns:
        A string summary of the results or an error message.
    """
    try:
        # Basic safety check to prevent modification queries
        if not query.strip().lower().startswith("select"):
            return "Error: Only SELECT queries are allowed."
            
        connection = mysql.connector.connect(
            host='mysql-rfam-public.ebi.ac.uk',
            user='rfamro',
            port=4497,
            database='Rfam'
        )
        
        cursor = connection.cursor(dictionary=True)
        
        # Limit results to prevent overwhelming the context
        if "limit" not in query.lower():
            query += " LIMIT 10"
            
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        if not results:
            return "No results found."
            
        return str(results)
        
    except Exception as e:
        return f"Error executing query: {str(e)}"

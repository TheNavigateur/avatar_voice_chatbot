import mysql.connector

def get_schema():
    try:
        connection = mysql.connector.connect(
            host='mysql-rfam-public.ebi.ac.uk',
            user='rfamro',
            port=4497,
            database='Rfam'
        )
        
        cursor = connection.cursor()
        
        # Get all tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        schema_info = ""
        
        # For this task, we'll focus on the main 'family' table and maybe a few others relevant to 'families'
        # Fetching schema for ALL tables might be too much context, let's start with 'family', 'clan', 'taxonomy' if they exist.
        # Let's just list all tables first to see what's available, then describe the important ones.
        
        important_tables = ['family', 'clan', 'taxonomy', 'rfamseq']
        
        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            if table_name in important_tables:
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                schema_info += f"\nTable: {table_name}\n"
                for col in columns:
                    # Field, Type, Null, Key, Default, Extra
                    schema_info += f"  - {col[0]} ({col[1]})\n"
        
        print(schema_info)
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_schema()

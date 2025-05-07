import sqlite3

DATABASE_NAME = 'visual_collection.db'

"""
Collection Database

| id | name               | folder path           | cover image         | Creation Date  | tags     |
| -- | ------------------ | --------------------- | ------------------- | -------------- | -------- |
| 1  | My Collection A    | /path/to/folderA      | /images/coverA.jpg  | 2025-05-07     | 1, 2     |
| 2  | Old Posters        | /path/to/folderB      | /images/coverB.png  | 2024-12-15     | 3        |
| 3  | Rare Objects       | /path/to/folderC      | /images/coverC.webp | 2023-10-21     | 2, 4     |

Tag Database

| tag_id | name            |
| ------ | --------------- |
| 1      | illustration    |
| 2      | 80s             |
| 3      | movie poster    |
| 4      | antique object  |

"""

def initialize_database():
    """
    Initializes the SQLite database by creating necessary tables if they don't already exist.
    Tables created:
    - Collections: Stores information about each collection (name, folder path, cover image, etc.).
    - Tags: Stores unique tag names.
    - CollectionTags: A many-to-many relationship table linking collections to tags.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create Collections table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        chemin_dossier TEXT NOT NULL,
        image_couverture TEXT,
        date_creation DATE DEFAULT CURRENT_TIMESTAMP,
        tags TEXT
    )
    ''')

    # Create Tags table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Tags (
        tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_tag TEXT NOT NULL UNIQUE
    )
    ''')

    # Create CollectionTags table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS CollectionTags (
        collection_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        PRIMARY KEY (collection_id, tag_id),
        FOREIGN KEY (collection_id) REFERENCES Collections (id),
        FOREIGN KEY (tag_id) REFERENCES Tags (tag_id)
    )
    ''')

    conn.commit()
    conn.close()

def add_collection_to_db(nom, chemin_dossier, image_couverture, tags_str):
    """
    Adds a new collection to the database along with its associated tags.

    Args:
        nom (str): The name of the collection.
        chemin_dossier (str): The file system path to the collection's folder.
        image_couverture (str): The file system path to the collection's cover image.
        tags_str (str): A comma-separated string of tags associated with the collection.
        Tags that do not exist will be created.

    Returns:
        int or None: The ID of the newly created collection if successful, otherwise None.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    collection_id = None
    processed_tag_ids = []

    try:
        # 1. Add/Get Tags and their IDs
        if tags_str:
            tag_names = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            for tag_name in tag_names:
                # Check if tag exists
                cursor.execute("SELECT tag_id FROM Tags WHERE nom_tag = ?", (tag_name,))
                tag_row = cursor.fetchone()
                if tag_row:
                    tag_id = tag_row[0]
                else:
                    # Add new tag
                    cursor.execute("INSERT INTO Tags (nom_tag) VALUES (?)", (tag_name,))
                    tag_id = cursor.lastrowid
                if tag_id:
                    processed_tag_ids.append(str(tag_id)) # Store as string for joining

        # 2. Insert the Collection with comma-separated tag IDs
        tags_ids_string = ",".join(processed_tag_ids)
        cursor.execute('''
        INSERT INTO Collections (nom, chemin_dossier, image_couverture, tags)
        VALUES (?, ?, ?, ?)
        ''', (nom, chemin_dossier, image_couverture, tags_ids_string))
        collection_id = cursor.lastrowid

        # 3. Insert CollectionTags
        for tag_id in processed_tag_ids:
            cursor.execute("INSERT INTO CollectionTags (collection_id, tag_id) VALUES (?, ?)", (collection_id, tag_id))

        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback() # Rollback changes on error
    finally:
        conn.close()

    return collection_id

def get_all_tags():
    """
    Retrieves all unique tag names from the Tags table, ordered alphabetically.

    Returns:
        list: A list of strings, where each string is a tag name.
    """
    conn = sqlite3.connect('visual_collection.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nom_tag FROM Tags ORDER BY nom_tag")
    tags = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tags

def add_new_tag(nom_tag):
    """
    Adds a new tag to the Tags table if it doesn't already exist (case-insensitive check).

    Args:
        nom_tag (str): The name of the tag to add.

    Returns:
        bool: True if the tag was successfully added, False if the tag already exists or an error occurred.
    """
    conn = sqlite3.connect('visual_collection.db')
    cursor = conn.cursor()
    try:
        # Check if tag already exists (case-insensitive check recommended for tags)
        cursor.execute("SELECT tag_id FROM Tags WHERE LOWER(nom_tag) = LOWER(?)", (nom_tag,))
        existing_tag = cursor.fetchone()
        if existing_tag:
            print(f"Tag '{nom_tag}' already exists with ID {existing_tag[0]}.")
            conn.close()
            return False # Indicate tag was not added because it exists

        cursor.execute("INSERT INTO Tags (nom_tag) VALUES (?)", (nom_tag,))
        conn.commit()
        print(f"Tag '{nom_tag}' added with ID {cursor.lastrowid}.")
        conn.close()
        return True # Indicate success
    except sqlite3.IntegrityError:
        # This might happen if there's a unique constraint and the LOWER() check missed a case
        print(f"Integrity error: Tag '{nom_tag}' likely already exists.")
        conn.close()
        return False
    except Exception as e:
        print(f"Error adding new tag '{nom_tag}' to database: {e}")
        conn.close()
        return False

def get_all_collections():
    """
    Retrieves all collections from the database, along with their associated tags (concatenated into a string).
    Collections are ordered by creation date in descending order.

    Returns:
        list: A list of tuples. Each tuple represents a collection and contains:
            (id, name, cover_image_path, folder_path, concatenated_tags_string or None)
    """
    conn = sqlite3.connect('visual_collection.db')
    cursor = conn.cursor()
    query = """
    SELECT
        c.id,
        c.nom,
        c.image_couverture,
        c.chemin_dossier,
        GROUP_CONCAT(t.nom_tag) AS tags_concatenes
    FROM
        Collections c
    LEFT JOIN
        CollectionTags ct ON c.id = ct.collection_id
    LEFT JOIN
        Tags t ON ct.tag_id = t.tag_id
    GROUP BY
        c.id, c.nom, c.image_couverture, c.chemin_dossier, c.date_creation
    ORDER BY
        c.date_creation DESC;
    """
    cursor.execute(query)
    collections = cursor.fetchall() # Chaque ligne sera (id, nom, image_couverture, tags_string_ou_None)
    conn.close()
    return collections

if __name__ == '__main__':
    """
    Main execution block to initialize the database when the script is run directly.
    """
    initialize_database()
    print(f"Database '{DATABASE_NAME}' initialized.")
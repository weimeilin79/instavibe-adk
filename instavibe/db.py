# spanner_data_fetchers.py

import os
import traceback
from datetime import datetime,
import json # For example usage printing

from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
from google.api_core import exceptions

# --- Spanner Configuration ---
INSTANCE_ID = os.environ.get("SPANNER_INSTANCE_ID", "instavibe-graph-instance")
DATABASE_ID = os.environ.get("SPANNER_DATABASE_ID", "graphdb")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

if not PROJECT_ID:
    print("Warning: GOOGLE_CLOUD_PROJECT environment variable not set.")

# --- Spanner Client Initialization ---
db = None
spanner_client = None
try:
    if PROJECT_ID:
        spanner_client = spanner.Client(project=PROJECT_ID)
        instance = spanner_client.instance(INSTANCE_ID)
        database = instance.database(DATABASE_ID)
        print(f"Attempting to connect to Spanner: {instance.name}/databases/{database.name}")

        if not database.exists():
             print(f"Error: Database '{database.name}' does not exist in instance '{instance.name}'.")
             db = None
        else:
            print("Spanner database connection check successful.")
            db = database
    else:
        print("Skipping Spanner client initialization due to missing GOOGLE_CLOUD_PROJECT.")

except exceptions.NotFound:
    print(f"Error: Spanner instance '{INSTANCE_ID}' not found in project '{PROJECT_ID}'.")
    db = None
except Exception as e:
    print(f"An unexpected error occurred during Spanner initialization: {e}")
    db = None

# --- Utility Function (Graph Query Specific) ---

def run_graph_query(db_instance, graph_sql, params=None, param_types=None, expected_fields=None):
    """
    Executes a Spanner Graph Query (GQL).

    Args:
        db_instance: The Spanner database object.
        graph_sql (str): The GQL query string (starting with 'Graph ...').
        params (dict, optional): Dictionary of query parameters.
        param_types (dict, optional): Dictionary mapping param names to Spanner types.
        expected_fields (list[str], optional): Expected column names in order.

    Returns:
        list[dict]: A list of dictionaries representing the rows, or None on error.
    """
    if not db_instance:
        print("Error: Database connection is not available.")
        return None

    results_list = []
    print(f"--- Executing Graph Query ---")
    # print(f"GQL: {graph_sql}") # Uncomment for verbose query logging

    try:
        with db_instance.snapshot() as snapshot:
            # execute_sql handles both SQL and Graph Queries
            results = snapshot.execute_sql(
                graph_sql,
                params=params,
                param_types=param_types
            )

            field_names = expected_fields
            if not field_names:
                 print("Error: expected_fields must be provided to run_graph_query.")
                 return None

            for row in results:
                if len(field_names) != len(row):
                     print(f"Warning: Mismatch between field names ({len(field_names)}) and row values ({len(row)}). Skipping row: {row}")
                     continue
                results_list.append(dict(zip(field_names, row)))

            # print(f"Graph Query successful, fetched {len(results_list)} rows.") # Uncomment for verbose success logging

    except (exceptions.NotFound, exceptions.PermissionDenied, exceptions.InvalidArgument) as spanner_err:
        # InvalidArgument might occur if graph syntax is wrong or graph doesn't exist
        print(f"Spanner Graph Query Error ({type(spanner_err).__name__}): {spanner_err}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during graph query execution or processing: {e}")
        traceback.print_exc()
        return None

    return results_list


# --- Data Fetching Functions using Graph Queries ---

def get_person_attended_events_json(db_instance, person_id):
    """
    Fetches events attended by a specific person using Graph Query.

    Args:
        db_instance: The Spanner database object.
        person_id (str): The ID of the person.

    Returns:
        list[dict] or None: List of event dictionaries with ISO date strings,
                           or None if an error occurs.
    """
    if not db_instance: return None

    # Graph Query: Find Person node, follow 'Attended' edge to Event node
    graph_sql = """
        Graph SocialGraph
        MATCH (p:Person)-[att:Attended]->(e:Event)
        WHERE p.person_id = @person_id
        RETURN e.event_id, e.name, e.event_date, att.attendance_time
        ORDER BY e.event_date DESC
    """
    params = {"person_id": person_id}
    param_types_map = {"person_id": param_types.STRING}
    fields = ["event_id", "name", "event_date", "attendance_time"] # Must match RETURN

    results = run_graph_query(db_instance, graph_sql, params=params, param_types=param_types_map, expected_fields=fields)

    if results is None:
        return None

    # Convert datetime objects to ISO format strings
    for event in results:
        if isinstance(event.get('event_date'), datetime):
            event['event_date'] = event['event_date'].isoformat()
        if isinstance(event.get('attendance_time'), datetime):
            event['attendance_time'] = event['attendance_time'].isoformat()

    return results


def get_all_posts_json(db_instance, limit=100):
    """
    Fetches all available posts with author name using Graph Query.

    Args:
        db_instance: The Spanner database object.
        limit (int): Maximum number of posts to fetch.

    Returns:
        list[dict] or None: List of post dictionaries with ISO date strings,
                           or None if an error occurs.
    """
    if not db_instance: return None

    # Graph Query: Find Person nodes that 'Wrote' a Post node
    graph_sql = """
        Graph SocialGraph
        MATCH (author:Person)-[w:Wrote]->(post:Post)
        RETURN post.post_id, post.author_id, post.text, post.sentiment, post.post_timestamp, author.name AS author_name
        ORDER BY post.post_timestamp DESC
        LIMIT @limit
    """
    params = {"limit": limit}
    param_types_map = {"limit": param_types.INT64}
    fields = ["post_id", "author_id", "text", "sentiment", "post_timestamp", "author_name"] # Must match RETURN

    results = run_graph_query(db_instance, graph_sql, params=params, param_types=param_types_map, expected_fields=fields)

    if results is None:
        return None

    # Convert datetime objects to ISO format strings
    for post in results:
        if isinstance(post.get('post_timestamp'), datetime):
            post['post_timestamp'] = post['post_timestamp'].isoformat()

    return results


def get_person_friends_json(db_instance, person_id):
    """
    Fetches friends for a specific person using Graph Query.

    Args:
        db_instance: The Spanner database object.
        person_id (str): The ID of the person.

    Returns:
        list[dict] or None: List of friend dictionaries ({person_id, name}),
                           or None if an error occurs.
    """
    if not db_instance: return None

    # Graph Query: Use undirected match for Friendship edge
    # Assumes the graph engine correctly interprets the underlying Friendship table structure
    graph_sql = """
        Graph SocialGraph
        MATCH (p:Person {person_id: @person_id})-[f:Friendship]-(friend:Person)
        RETURN DISTINCT friend.person_id, friend.name
        ORDER BY friend.name
    """
    params = {"person_id": person_id}
    param_types_map = {"person_id": param_types.STRING}
    fields = ["person_id", "name"] # Must match RETURN

    results = run_graph_query(db_instance, graph_sql, params=params, param_types=param_types_map, expected_fields=fields)

    # No date conversion needed here
    return results


# --- Example Usage (if run directly) ---
if __name__ == "__main__":
    if db:
        print("\n--- Testing Graph Data Fetching Functions ---")

        # Replace with a valid person_id from your database
        test_person_id = "p1" # Example: Assuming 'p1' is Alice's ID

        print(f"\n1. Fetching events attended by Person ID: {test_person_id}")
        attended_events = get_person_attended_events_json(db, test_person_id)
        if attended_events is not None:
            print(json.dumps(attended_events, indent=2))
        else:
            print("Failed to fetch attended events.")

        print("\n2. Fetching all posts (limit 10)")
        all_posts = get_all_posts_json(db, limit=10)
        if all_posts is not None:
            print(json.dumps(all_posts, indent=2))
        else:
            print("Failed to fetch all posts.")

        print(f"\n3. Fetching friends for Person ID: {test_person_id}")
        friends = get_person_friends_json(db, test_person_id)
        if friends is not None:
            print(json.dumps(friends, indent=2))
        else:
            print("Failed to fetch friends.")

    else:
        print("\nCannot run examples: Spanner database connection not established.")
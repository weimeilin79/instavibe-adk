import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, abort, flash, request, jsonify
from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
from google.api_core import exceptions
import humanize 
import uuid
import traceback
from dateutil import parser 
from ally_routes import ally_bp 


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_secret_key_for_dev") 
app.register_blueprint(ally_bp)

load_dotenv()
# --- Spanner Configuration ---
INSTANCE_ID = "instavibe-graph-instance" # Replace if different
DATABASE_ID = "graphdb" # Replace if different
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = os.environ.get("APP_PORT","8080")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
GOOGLE_MAPS_MAP_KEY = os.environ.get('GOOGLE_MAPS_MAP_ID')


if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")

# --- Spanner Client Initialization ---
db = None
try:
    spanner_client = spanner.Client(project=PROJECT_ID)
    instance = spanner_client.instance(INSTANCE_ID)
    database = instance.database(DATABASE_ID)
    print(f"Attempting to connect to Spanner: {instance.name}/databases/{database.name}")

    # Ensure database exists - crucial check
    if not database.exists():
         print(f"Error: Database '{database.name}' does not exist in instance '{instance.name}'.")
         print("Please create the database and the required tables/schema.")
         # You might want to exit or handle this more gracefully depending on deployment
         # For now, we'll let it fail later if db is None
    else:
        print("Database connection check successful (database exists).")
        db = database # Assign database object if it exists

except exceptions.NotFound:
    print(f"Error: Spanner instance '{INSTANCE_ID}' not found in project '{PROJECT_ID}'.")
    # Handle error appropriately - exit, default behavior, etc.
except Exception as e:
    print(f"An unexpected error occurred during Spanner initialization: {e}")
    # Handle error

def run_query(sql, params=None, param_types=None, expected_fields=None): # Add expected_fields
    """
    Executes a SQL query against the Spanner database.

    Args:
        sql (str): The SQL query string.
        params (dict, optional): Dictionary of query parameters. Defaults to None.
        param_types (dict, optional): Dictionary mapping parameter names to their
                                      Spanner types (e.g., spanner.param_types.STRING).
                                      Defaults to None.
        expected_fields (list[str], optional): A list of strings representing the
                                                expected column names in the order
                                                they appear in the SELECT statement.
                                                Required if results.fields fails.
    """
    if not db:
        print("Error: Database connection is not available.")
        raise ConnectionError("Spanner database connection not initialized.")

    results_list = []
    print(f"--- Executing SQL ---")
    print(f"SQL: {sql}")
    if params:
        print(f"Params: {params}")
    print("----------------------")

    try:
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql(
                sql,
                params=params,
                param_types=param_types
            )

            # --- MODIFICATION START ---
            # Define field names based on the expected_fields argument
            # This avoids accessing results.fields which caused the error
            field_names = expected_fields
            if not field_names:
                 # Fallback or raise error if expected_fields were not provided
                 # For now, let's try the potentially failing way if not provided
                 print("Warning: expected_fields not provided to run_query. Attempting dynamic lookup.")
                 try:
                     field_names = [field.name for field in results.fields]
                 except AttributeError as e:
                     print(f"Error accessing results.fields even as fallback: {e}")
                     print("Cannot process results without field names.")
                     # Decide: raise error or return empty list?
                     raise ValueError("Could not determine field names for query results.") from e


            print(f"Using field names: {field_names}")
            # --- MODIFICATION END ---

            for row in results:
                # Now zip the known field names with the row values (which are lists)
                if len(field_names) != len(row):
                     print(f"Warning: Mismatch between number of field names ({len(field_names)}) and row values ({len(row)})")
                     print(f"Fields: {field_names}")
                     print(f"Row: {row}")
                     # Skip this row or handle error appropriately
                     continue # Skip malformed row for now
                results_list.append(dict(zip(field_names, row)))

            print(f"Query successful, fetched {len(results_list)} rows.")

    except (exceptions.NotFound, exceptions.PermissionDenied, exceptions.InvalidArgument) as spanner_err:
        print(f"Spanner Error ({type(spanner_err).__name__}): {spanner_err}")
        flash(f"Database error: {spanner_err}", "danger")
        return []
    except ValueError as e: # Catch the ValueError we might raise above
         print(f"Query Processing Error: {e}")
         flash("Internal error processing query results.", "danger")
         return []
    except Exception as e:
        print(f"An unexpected error occurred during query execution or processing: {e}")
        traceback.print_exc()
        flash(f"An unexpected server error occurred while fetching data.", "danger")
        raise e

    return results_list

# --- HOW TO CALL IT ---

def get_all_posts_with_author_db():
    """Fetch all posts and join with author information from Spanner."""
    sql = """
        SELECT
            p.post_id, p.author_id, p.text, p.sentiment, p.post_timestamp,
            author.name as author_name
        FROM Post AS p
        JOIN Person AS author ON p.author_id = author.person_id
        ORDER BY p.post_timestamp DESC
    """
    # Define the fields exactly as they appear in the SELECT statement
    fields = ["post_id", "author_id", "text", "sentiment", "post_timestamp", "author_name"]
    return run_query(sql, expected_fields=fields) # Pass the list here

def get_person_db(person_id):
    """Fetch a single person's details from Spanner."""
    sql = """
        SELECT person_id, name, age
        FROM Person
        WHERE person_id = @person_id
    """
    params = {"person_id": person_id}
    param_types_map = {"person_id": param_types.STRING} # Renamed variable
    fields = ["person_id", "name", "age"]
    results = run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)
    return results[0] if results else None

def get_posts_by_person_db(person_id):
    """Fetch posts written by a specific person from Spanner."""
    sql = """
        SELECT
            p.post_id, p.author_id, p.text, p.sentiment, p.post_timestamp,
            author.name as author_name
        FROM Post AS p
        JOIN Person AS author ON p.author_id = author.person_id
        WHERE p.author_id = @person_id
        ORDER BY p.post_timestamp DESC
    """
    params = {"person_id": person_id}
    param_types_map = {"person_id": param_types.STRING}
    fields = ["post_id", "author_id", "text", "sentiment", "post_timestamp", "author_name"]
    return run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)

def get_friends_db(person_id):
    """Fetch friends of a specific person from Spanner."""
    sql = """
        SELECT DISTINCT
            friend.person_id, friend.name
        FROM Friendship AS f
        JOIN Person AS friend ON
            (f.person_id_a = @person_id AND f.person_id_b = friend.person_id) OR
            (f.person_id_b = @person_id AND f.person_id_a = friend.person_id)
        WHERE f.person_id_a = @person_id OR f.person_id_b = @person_id
        ORDER BY friend.name
    """
    params = {"person_id": person_id}
    param_types_map = {"person_id": param_types.STRING}
    fields = ["person_id", "name"]
    return run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)


def get_all_events_with_attendees_db():
    """Fetch all events and their attendees from Spanner."""
    # Get all events first
    event_sql = """
        SELECT event_id, name, event_date
        FROM Event
        ORDER BY event_date DESC
        LIMIT 50
    """
    event_fields = ["event_id", "name", "event_date"]
    events = run_query(event_sql, expected_fields=event_fields)
    if not events:
        return []

    events_with_attendees = {event['event_id']: {'details': event, 'attendees': []} for event in events}
    event_ids = list(events_with_attendees.keys())

    # Fetch attendees
    attendee_sql = """
        SELECT
            a.event_id,
            p.person_id, p.name
        FROM Attendance AS a
        JOIN Person AS p ON a.person_id = p.person_id
        WHERE a.event_id IN UNNEST(@event_ids)
        ORDER BY a.event_id, p.name
    """
    params = {"event_ids": event_ids}
    param_types_map = {"event_ids": param_types.Array(param_types.STRING)}
    attendee_fields = ["event_id", "person_id", "name"]
    all_attendees = run_query(attendee_sql, params=params, param_types=param_types_map, expected_fields=attendee_fields)

    for attendee in all_attendees:
        event_id = attendee['event_id']
        if event_id in events_with_attendees:
            # No change needed here, attendee is already a dict
            events_with_attendees[event_id]['attendees'].append(attendee)

    return [events_with_attendees[event['event_id']] for event in events]

def get_event_details_with_locations_attendees_db(event_id):
    """
    Fetch full details for a single event, including its description,
    locations, and attendees.
    """
    if not db:
        raise ConnectionError("Spanner database connection not initialized.")

    event_details = {}

    # 1. Fetch Event basic details (including new description)
    event_sql = """
        SELECT event_id, name, description, event_date
        FROM Event
        WHERE event_id = @event_id
    """
    params = {"event_id": event_id}
    param_types_map = {"event_id": param_types.STRING}
    event_fields = ["event_id", "name", "description", "event_date"]
    event_result = run_query(event_sql, params=params, param_types=param_types_map, expected_fields=event_fields)

    if not event_result:
        return None # Event not found
    event_details = event_result[0]

    # 2. Fetch Event Locations
    locations_sql = """
        SELECT l.location_id, l.name, l.description, l.latitude, l.longitude, l.address
        FROM Location AS l
        JOIN EventLocation AS el ON l.location_id = el.location_id
        WHERE el.event_id = @event_id
        ORDER BY l.name
    """
    # Params and param_types_map are the same as for event_sql
    location_fields = ["location_id", "name", "description", "latitude", "longitude", "address"]
    event_details["locations"] = run_query(locations_sql, params=params, param_types=param_types_map, expected_fields=location_fields)

    # 3. Fetch Event Attendees
    attendees_sql = """
        SELECT p.person_id, p.name
        FROM Person AS p
        JOIN Attendance AS a ON p.person_id = a.person_id
        WHERE a.event_id = @event_id
        ORDER BY p.name
    """
    # Params and param_types_map are the same
    attendee_fields = ["person_id", "name"]
    event_details["attendees"] = run_query(attendees_sql, params=params, param_types=param_types_map, expected_fields=attendee_fields)

    # Convert datetimes to ISO format if they are not already strings
    if isinstance(event_details.get('event_date'), datetime):
        event_details['event_date'] = event_details['event_date'].isoformat()

    # Ensure locations have float for lat/lon if they are Decimal or other numeric types
    for loc in event_details.get("locations", []):
        if loc.get("latitude") is not None: loc["latitude"] = float(loc["latitude"])
        if loc.get("longitude") is not None: loc["longitude"] = float(loc["longitude"])
    return event_details


# --- Custom Jinja Filter ---
@app.template_filter('humanize_datetime')
def _jinja2_filter_humanize_datetime(value, default="just now"):
    """
    Convert a datetime object to a human-readable relative time string.
    e.g., '5 minutes ago', '2 hours ago', '3 days ago'
    """
    if not value:
        return default
   
    dt_object = None
    if isinstance(value, str):
        try:
            # Attempt to parse ISO 8601 format.
            # .replace('Z', '+00:00') handles UTC 'Z' suffix for fromisoformat.
            dt_object = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            # Fallback to dateutil.parser for more general string formats
            try:
                dt_object = parser.parse(value)
            except (parser.ParserError, TypeError, ValueError) as e:
                app.logger.warning(f"Could not parse date string '{value}' in humanize_datetime: {e}")
                return str(value) # Return original string if unparseable
    elif isinstance(value, datetime):
        dt_object = value
    else:
        # If not a string or datetime, return its string representation
        return str(value)

    if dt_object is None: # Should have been handled, but as a safeguard
        app.logger.warning(f"Date value '{value}' resulted in None dt_object in humanize_datetime.")
        return str(value)

    now = datetime.now(timezone.utc)
    # Use dt_object for all datetime operations from here
    if dt_object.tzinfo is None or dt_object.tzinfo.utcoffset(dt_object) is None:
        # If dt_object is naive, assume it's UTC
        dt_object = dt_object.replace(tzinfo=timezone.utc)
    else:
        # Convert aware dates to UTC
        dt_object = dt_object.astimezone(timezone.utc)

    try:
        return humanize.naturaltime(now - dt_object)
    except TypeError:
        # Fallback or handle error if date calculation fails
        return dt_object.strftime("%Y-%m-%d %H:%M")


def get_person_by_name_db(name):
    """Fetch a person's ID by their name from Spanner."""
    if not db:
        print("Error: Database connection is not available.")
        raise ConnectionError("Spanner database connection not initialized.")

    sql = "SELECT person_id FROM Person WHERE name = @name LIMIT 1"
    params = {"name": name}
    param_types_map = {"name": param_types.STRING}
    fields = ["person_id"] # Expected field from the SELECT
    try:
        results = run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)
        return results[0]['person_id'] if results else None
    except Exception as e:
        print(f"Error fetching person by name '{name}': {e}")
        # Optionally re-raise or return None based on desired error handling
        raise e # Re-raise to be caught by the API endpoint handler

# --- Helper function to insert a post ---
def add_post_db(post_id, author_id, text, sentiment=None):
    """Inserts a new post into the Spanner database."""
    if not db:
        print("Error: Database connection is not available for insert.")
        raise ConnectionError("Spanner database connection not initialized.")

    def _insert_post(transaction):
        transaction.insert(
            table="Post",
            columns=[
                "post_id", "author_id", "text", "sentiment",
                "post_timestamp", "create_time"
            ],
            values=[(
                post_id, author_id, text, sentiment,
                datetime.now(timezone.utc), # Use current UTC time for post_timestamp
                spanner.COMMIT_TIMESTAMP   # Use commit time for create_time
            )]
        )
        print(f"Transaction attempting to insert post_id: {post_id}")

    try:
        db.run_in_transaction(_insert_post)
        print(f"Successfully inserted post_id: {post_id}")
        return True
    except Exception as e:
        print(f"Error inserting post (id: {post_id}): {e}")
        # Log the full traceback for detailed debugging if needed
        # traceback.print_exc()
        return False # Indicate failure

def add_full_event_with_details_db(event_id, event_name, description, event_date, locations_data, attendee_ids):
    """
    Inserts a new event with its title, description, multiple locations,
    and its first attendee into Spanner within a transaction.

    Args:
        event_id (str): The unique ID for the new event.
        event_name (str): Name of the event (maps to Event.name).
        description (str): Description of the event.
        event_date (datetime): Date/time of the event (timezone-aware recommended).
        locations_data (list[dict]): A list of location dictionaries. Each dict should contain:
                                     'name', 'description', 'latitude', 'longitude', 'address'.
        attendee_ids (list[str]): A list of person_ids for the attendees.

    Returns:
        bool: True if the transaction was successful, False otherwise.
    """
    if not db:
        print("Error: Database connection is not available for full event insert.")
        raise ConnectionError("Spanner database connection not initialized.")

    def _insert_event_and_attendee(transaction):
        # Insert into Event table (Simplified Schema)
        transaction.insert(
            table="Event",
            columns=[
                "event_id", "name", "description", "event_date", "create_time"
            ],
            values=[(
                event_id, event_name, description, event_date,
                spanner.COMMIT_TIMESTAMP
            )]
        )
        print(f"Transaction attempting to insert event_id: {event_id}")

        # Insert Locations and EventLocation links
        for loc_data in locations_data:
            location_id = str(uuid.uuid4())
            transaction.insert(
                table="Location",
                columns=["location_id", "name", "description", "latitude", "longitude", "address", "create_time"],
                values=[(
                    location_id, loc_data.get("name"), loc_data.get("description"),
                    float(loc_data.get("latitude", 0.0)), float(loc_data.get("longitude", 0.0)), # Ensure float
                    loc_data.get("address"), spanner.COMMIT_TIMESTAMP
                )]
            )
            print(f"Transaction attempting to insert location_id: {location_id} for event {event_id}")
            transaction.insert(
                table="EventLocation",
                columns=["event_id", "location_id", "create_time"],
                values=[(event_id, location_id, spanner.COMMIT_TIMESTAMP)]
            )
            print(f"Transaction attempting to link event {event_id} with location {location_id}")

        # Insert each attendee into Attendance table
        if attendee_ids:
            for attendee_id_to_add in attendee_ids:
                transaction.insert(
                    table="Attendance",
                    columns=["event_id", "person_id", "attendance_time"],
                    values=[(event_id, attendee_id_to_add, spanner.COMMIT_TIMESTAMP)]
                )
                print(f"Transaction attempting to insert attendee {attendee_id_to_add} for event {event_id} into Attendance")

    try:
        db.run_in_transaction(_insert_event_and_attendee)
        print(f"Successfully inserted event {event_id} with details and attendees {attendee_ids}")
        return True
    except Exception as e:
        print(f"Error inserting full event (event_id: {event_id}, attendee_ids: {attendee_ids}): {e}")
        traceback.print_exc() # Log detailed error
        return False # Indicate failure

# --- Routes ---
@app.route('/')
def home():
    """Home page: Shows all posts and the events panel."""
    all_posts = []
    all_events_attendance = [] # Initialize

    if not db:
        flash("Database connection not available. Cannot load page data.", "danger")
    else:
        try:
            # Fetch both posts and events
            all_posts = get_all_posts_with_author_db()
            all_events_attendance = get_all_events_with_attendees_db() # Fetch events
        except Exception as e:
             flash(f"Failed to load page data: {e}", "danger")
             # Ensure variables are defined even on error
             all_posts = []
             all_events_attendance = []

    return render_template(
        'index.html',
        posts=all_posts,
        all_events_attendance=all_events_attendance, # Pass events to template
        google_maps_api_key=GOOGLE_MAPS_API_KEY, # For potential future use on home page
        google_maps_map_id=GOOGLE_MAPS_MAP_KEY # Pass it to the template
    )


@app.route('/person/<string:person_id>')
def person_profile(person_id):
    """Person profile page, fetching data from Spanner."""
    if not db:
        flash("Database connection not available. Cannot load profile.", "danger")
        abort(503) # Service Unavailable

    try:
        person = get_person_db(person_id)
        if not person:
            abort(404) # Person not found

        person_posts = get_posts_by_person_db(person_id)
        friends = get_friends_db(person_id)
        all_events_attendance = get_all_events_with_attendees_db()

    except Exception as e:
         flash(f"Failed to load profile data: {e}", "danger")
         # Redirect to home or show an error page might be better than aborting
         return render_template('person.html', person=person, person_posts=[], friends=[], all_events_attendance=[], error=True)


    return render_template(
        'person.html',
        person=person,
        person_posts=person_posts,
        friends=friends,
        all_events_attendance=all_events_attendance
    )

@app.route('/event/<string:event_id>')
def event_detail_page(event_id):
    """Event detail page showing description, locations on a map, and attendees."""
    if not db:
        flash("Database connection not available. Cannot load event details.", "danger")
        abort(503) # Service Unavailable

    if not GOOGLE_MAPS_API_KEY:
        flash("Google Maps API Key is not configured. Map functionality will be disabled.", "warning")

    event_data = None
    try:
        event_data = get_event_details_with_locations_attendees_db(event_id)
        if not event_data:
            abort(404) # Event not found
    except Exception as e:
        flash(f"Failed to load event data: {e}", "danger")
        # Log the error for debugging
        print(f"Error fetching event {event_id}: {e}")
        traceback.print_exc()
        # Render the page with an error state or redirect
        return render_template('event_detail.html', event=None, error=True, google_maps_api_key=GOOGLE_MAPS_API_KEY)

    return render_template('event_detail.html', event=event_data, google_maps_api_key=GOOGLE_MAPS_API_KEY)


@app.route('/api/posts', methods=['POST'])
def add_post_api():
    """
    API endpoint to add a new post.
    Expects JSON body: {"author_name": "...", "text": "...", "sentiment": "..." (optional)}
    """
    if not db:
        return jsonify({"error": "Database connection not available"}), 503 # Service Unavailable

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400
    if 'author_name' not in data or 'text' not in data:
        return jsonify({"error": "Missing 'author_name' or 'text' in request body"}), 400

    author_name = data['author_name']
    text = data['text']
    sentiment = data.get('sentiment') # Optional, defaults to None if not provided

    # Basic input validation
    if not isinstance(author_name, str) or not author_name.strip():
         return jsonify({"error": "'author_name' must be a non-empty string"}), 400
    if not isinstance(text, str) or not text.strip():
         return jsonify({"error": "'text' must be a non-empty string"}), 400
    if sentiment is not None and not isinstance(sentiment, str):
         return jsonify({"error": "'sentiment' must be a string if provided"}), 400

    try:
        # 1. Find the author_id using the provided name
        author_id = get_person_by_name_db(author_name)
        if not author_id:
            return jsonify({"error": f"Author '{author_name}' not found"}), 404 # Not Found

        # 2. Generate a unique ID for the new post
        new_post_id = str(uuid.uuid4())

        # 3. Insert the post into the database
        success = add_post_db(
            post_id=new_post_id,
            author_id=author_id,
            text=text,
            sentiment=sentiment
        )

        if success:
            # 4. Return a success response
            post_data = {
                "message": "Post added successfully",
                "post_id": new_post_id,
                "author_id": author_id,
                "author_name": author_name, # Include for convenience
                "text": text,
                "sentiment": sentiment,
                # Provide an approximate timestamp (actual is set by DB)
                "post_timestamp": datetime.now(timezone.utc).isoformat()
            }
            return jsonify(post_data), 201 # 201 Created status code
        else:
            # Insertion failed for some reason (logged in add_post_db)
            return jsonify({"error": "Failed to save post to the database"}), 500 # Internal Server Error

    except ConnectionError as e:
         # Handle case where db connection failed specifically in this request path
         print(f"ConnectionError during post add: {e}")
         return jsonify({"error": "Database connection error during operation"}), 503
    except Exception as e:
        # Catch any other unexpected errors (e.g., from get_person_by_name_db)
        print(f"Unexpected error processing add post request: {e}")
        traceback.print_exc() # Log detailed error for server admin
        return jsonify({"error": "An internal server error occurred"}), 500



@app.route('/api/events', methods=['POST'])
def add_event_api():
    """
    API endpoint to add a new event and its first attendee (simplified schema).
    Expects JSON body: {
        "event_name": "...", // Name of the event
        "description": "...", // Detailed description
        "event_date": "YYYY-MM-DDTHH:MM:SSZ" or "YYYY-MM-DDTHH:MM:SS+HH:MM",
        "locations": [ // List of location objects
            {"name": "...", "description": "...", "latitude": 0.0, "longitude": 0.0, "address": "..."}
        ],
        "attendee_names": ["...", "..."] // List of attendee names
    }
    """
    if not db:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    # --- Input Validation (Simplified) ---
    required_fields = ["event_name", "description", "event_date", "locations", "attendee_names"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    event_name = data['event_name'] 
    description = data['description']
    event_date_str = data['event_date']
    locations_data = data['locations']
    attendee_names = data['attendee_names']

    # Basic type checks
    if not isinstance(event_name, str) or not event_name.strip(): 
         return jsonify({"error": "'event_name' must be a non-empty string"}), 400 
    if not isinstance(description, str):
         return jsonify({"error": "'description' must be a string"}), 400
    if not isinstance(event_date_str, str) or not event_date_str.strip():
         return jsonify({"error": "'event_date' must be a non-empty string"}), 400
    if not isinstance(attendee_names, list) or not attendee_names: # Ensure it's a non-empty list
         return jsonify({"error": "'attendee_names' must be a non-empty list of strings"}), 400
    for name in attendee_names:
        if not isinstance(name, str) or not name.strip():
            return jsonify({"error": "Each name in 'attendee_names' must be a non-empty string"}), 400
    if not isinstance(locations_data, list):
        return jsonify({"error": "'locations' must be a list"}), 400
    if not locations_data: 
        return jsonify({"error": "'locations' list cannot be empty"}), 400

    for i, loc in enumerate(locations_data):
        if not isinstance(loc, dict):
            return jsonify({"error": f"Each item in 'locations' must be an object (error at index {i})"}), 400
        loc_req_fields = ["name", "latitude", "longitude"]
        missing_loc_fields = [f for f in loc_req_fields if f not in loc or not str(loc[f]).strip()] # Check for presence and non-empty string for name
        if missing_loc_fields:
            return jsonify({"error": f"Location at index {i} missing required fields or has empty values: {', '.join(missing_loc_fields)}"}), 400
        try:
            float(loc["latitude"])
            float(loc["longitude"])
        except (ValueError, TypeError):
            return jsonify({"error": f"Location at index {i} has invalid latitude/longitude. Must be numbers."}), 400
        # Optional fields like description and address can be checked if needed
        if "description" in loc and not isinstance(loc["description"], str):
            return jsonify({"error": f"Location at index {i} 'description' must be a string if provided."}), 400
        if "address" in loc and not isinstance(loc["address"], str):
            return jsonify({"error": f"Location at index {i} 'address' must be a string if provided."}), 400

    # --- Process Inputs (Simplified) ---
    try:
        # Parse timestamp (ISO 8601 format expected)
        event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))

        # Spanner prefers timezone-aware datetimes.
        # Ensure it's aware (fromisoformat usually handles this if tz is present)
        if event_date.tzinfo is None or event_date.tzinfo.utcoffset(event_date) is None:
             # If input was naive, assume UTC as a sensible default
             print(f"Warning: Received naive datetime string '{event_date_str}'. Assuming UTC.")
             event_date = event_date.replace(tzinfo=timezone.utc)
        else:
             # Convert to UTC if it had a different offset
             event_date = event_date.astimezone(timezone.utc)


    except ValueError as e:
        return jsonify({"error": f"Invalid timestamp format for 'event_date'. Use ISO 8601 (e.g., YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DDTHH:MM:SS+HH:MM). Details: {e}"}), 400

    try:
        # 1. Find person_ids for all attendee names
        attendee_ids_to_add = []
        processed_attendees_info = []
        for attendee_name_str in attendee_names:
            attendee_id = get_person_by_name_db(attendee_name_str)
            if not attendee_id:
                return jsonify({"error": f"Attendee '{attendee_name_str}' not found"}), 404 # Not Found
            attendee_ids_to_add.append(attendee_id)
            processed_attendees_info.append({"id": attendee_id, "name": attendee_name_str})

        if not attendee_ids_to_add: # Should be caught by earlier validation, but good check
            return jsonify({"error": "No valid attendees found or provided."}), 400

        # 2. Generate a unique ID for the new event
        new_event_id = str(uuid.uuid4())

        # 3. Insert the event and all attendees atomically
        success = add_full_event_with_details_db(
            event_id=new_event_id,
            event_name=event_name,
            description=description,
            event_date=event_date,
            locations_data=locations_data,
            attendee_ids=attendee_ids_to_add,
        )

        if success:
            # 4. Return a success response
            event_data = {
                "message": "Event and attendees added successfully",
                "event_id": new_event_id,
                "event_name": event_name,
                "description": description,
                "event_date": event_date.isoformat(), # Return in ISO format
                "locations": locations_data, # Echo back the locations provided
                "attendees": processed_attendees_info # List of {id, name}
            }
            return jsonify(event_data), 201 # 201 Created status code
        else:
            # Insertion failed (error logged in helper function)
            return jsonify({"error": "Failed to save event and attendee to the database"}), 500 # Internal Server Error

    except ConnectionError as e:
         print(f"ConnectionError during event add: {e}")
         return jsonify({"error": "Database connection error during operation"}), 503
    except Exception as e:
        # Catch other unexpected errors
        print(f"Unexpected error processing add event request: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500


# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404 # You'll need to create 404.html

@app.errorhandler(500)
def internal_server_error(e):
     # Log the error e
     print(f"Internal Server Error: {e}")
     return render_template('500.html'), 500 # You'll need to create 500.html

@app.errorhandler(503)
def service_unavailable(e):
     # Log the error e
     print(f"Service Unavailable Error: {e}")
     return render_template('503.html'), 503 # You'll need to create 503.html





if __name__ == '__main__':
    # Check if db connection was successful before running
    if not db:
        print("\n--- Cannot start Flask app: Spanner database connection failed during initialization. ---")
        print("--- Please check GCP project, instance ID, database ID, permissions, and network connectivity. ---")
    else:
        print("\n--- Starting Flask Development Server ---")
        # Use debug=True only in development! It reloads code and provides better error pages.
        # Use host='0.0.0.0' to make it accessible on your network (e.g., from a VM)
        app.run(debug=True, host=APP_HOST, port=APP_PORT) # Changed port to avoid conflicts
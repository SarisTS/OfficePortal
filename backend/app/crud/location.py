from sqlalchemy.orm import Session
from app.models.location import Location
from app.schemas.location import LocationCreate, LocationUpdate, LocationOut, UserLocationOut
from fastapi import HTTPException, status
from sqlalchemy.sql import func
import json
from functools import lru_cache

def create_location(db: Session, payload: LocationCreate):
    new_location = Location(
        country_id       = payload.country_id,
        state_id         = payload.state_id,
        city_id          = payload.city_id,
        postal_code      = payload.postal_code
    )
    db.add(new_location)
    db.commit()
    db.refresh(new_location)

    names = resolve_location_names(location="city", id=new_location.city_id)

    new_location.country_name = names["country_name"]
    new_location.state_name   = names["state_name"]
    new_location.city_name    = names["city_name"]

    return new_location

def get_locations(db: Session, page: int = 1, limit: int = 10):
    query = db.query(Location).filter(Location.deleted_at.is_(None))
    total = query.count()
    return total, query.offset((page - 1) * limit).limit(limit).all()

def get_location_by_id(db: Session, location_id: int):
    data = db.query(Location).filter(Location.id == location_id, Location.deleted_at.is_(None)).first()
    names = resolve_location_names(location="city", id=data.city_id)

    data.country_name = names["country_name"]
    data.state_name   = names["state_name"]
    data.city_name    = names["city_name"]

    return data

def update_location(db: Session, location_id: int, payload: LocationUpdate):
    location = db.query(Location).filter(Location.id == location_id, Location.deleted_at.is_(None)).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    
    if payload.postal_code is not None:
        location.postal_code = payload.postal_code
    if payload.is_active is not None:
        location.is_active = payload.is_active
    if payload.country_id is not None:
        location.country_id = payload.country_id
    if payload.state_id is not None:
        location.state_id = payload.state_id
    if payload.city_id is not None:
        location.city_id = payload.city_id

    db.commit()
    db.refresh(location)

    names = resolve_location_names(location="city", id=location.city_id)

    location.country_name = names["country_name"]
    location.state_name   = names["state_name"]
    location.city_name    = names["city_name"]


    return location
    
def delete_location(db: Session, location_id: int):
    location = db.query(Location).filter(Location.id == location_id, Location.deleted_at.is_(None)).first()
    if not location:
        return None
    
    location.is_active = False
    location.is_deleted = True
    location.deleted_at = func.now()
    db.commit()
    db.refresh(location)
    return location
    

# Retrieval from JSON File
file="location.json"

def load_data():
    with open(file,"r",encoding="utf-8")as f:
        return json.load(f)
    
def get_json_countries():
    countries=load_data()
    return countries
    
def get_state_by_country_id(country_id:int):
    countries=load_data()
    for country in countries:
        if country.get("id")==country_id:
            return country.get("states",[])
    return None

def get_city_by_state_id(state_id:int):
    countries=load_data()

    for country in countries:
        for state in country.get("states",[]):
            if state.get("id")==state_id:
                return state.get("cities",[])
    return None

def resolve_location_names(location: str, id: int):
    data = load_data()

    country_name = None
    state_name = None
    city_name = None

    # COUNTRY lookup
    if location == "country":
        for country in data:
            if country["id"] == id:
                country_name = country["name"]
                break

    # STATE lookup (find parent country)
    elif location == "state":
        for country in data:
            for state in country.get("states", []):
                if state["id"] == id:
                    country_name = country["name"]
                    state_name = state["name"]
                    break
            if state_name:
                break

    # CITY lookup (find parent state + country)
    elif location == "city":
        for country in data:
            for state in country.get("states", []):
                for city in state.get("cities", []):
                    if city["id"] == id:
                        country_name = country["name"]
                        state_name = state["name"]
                        city_name = city["name"]
                        break
                if city_name:
                    break
            if city_name:
                break

    else:
        raise ValueError("location must be 'country', 'state', or 'city'")

    return {
        "country_name": country_name,
        "state_name": state_name,
        "city_name": city_name,
    }

@lru_cache
def build_lookup():
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    country_map = {}
    state_map   = {}
    city_map    = {}

    for country in data:
        country_map[country["id"]] = country["name"]
        for state in country.get("states", []):
            state_map[state["id"]] = state["name"]
            for city in state.get("cities", []):
                city_map[city["id"]] = city["name"]

    return country_map, state_map, city_map


def get_country_name(country_id: int) -> str | None:
    country_map, _, _ = build_lookup()
    return country_map.get(country_id)


def get_state_name(state_id: int) -> str | None:
    _, state_map, _ = build_lookup()
    return state_map.get(state_id)


def get_city_name(city_id: int) -> str | None:
    _, _, city_map = build_lookup()
    return city_map.get(city_id)

def map_location_out(location: Location) -> LocationOut:
    return LocationOut(
        id           = location.id,
        country_id   = location.country_id,
        state_id     = location.state_id,
        city_id      = location.city_id,
        country_name = get_country_name(location.country_id),
        state_name   = get_state_name(location.state_id),
        city_name    = get_city_name(location.city_id),
        postal_code  = location.postal_code,
        is_active    = location.is_active,
        created_at   = location.created_at,
        updated_at   = location.updated_at,
        deleted_at   = location.deleted_at
    )

def user_map_location_out(location: Location) -> UserLocationOut:
    return UserLocationOut(
        id           = location.id,
        country_id   = location.country_id,
        state_id     = location.state_id,
        city_id      = location.city_id,
        country_name = get_country_name(location.country_id),
        state_name   = get_state_name(location.state_id),
        city_name    = get_city_name(location.city_id),
        postal_code  = location.postal_code,
    )

def find_location_ids_by_search(search: str) -> set[int]:
    search = search.lower()
    countries = load_data()

    matched_location_ids = set()

    for country in countries:
        if search in country["name"].lower():
            matched_location_ids.add(country["id"])

        for state in country.get("states", []):
            if search in state["name"].lower():
                matched_location_ids.add(state["id"])

            for city in state.get("cities", []):
                if search in city["name"].lower():
                    matched_location_ids.add(city["id"])

    return matched_location_ids

"""def paginate(data : list,page : int = 1, limit : int = 10 ):
    start = (page-1) * limit
    end = start + limit
    items = data[start:end]
    return items, page, limit,len(data)"""

def validate_location_or_404(db: Session, location_id: int) -> Location:
    location = (
        db.query(Location)
        .filter(
            Location.id == location_id,
            Location.deleted_at.is_(None)
        )
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    return location
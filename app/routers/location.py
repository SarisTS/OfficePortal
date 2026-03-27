from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.database.database import get_db
from app.schemas.location import LocationCreate, LocationUpdate, LocationOut, JSONStateResponse,JSONCityResponse,JSONCountryResponse
from app.crud import location as crud
from app.utils.api_response import ApiResponse,PaginatedResponse

router = APIRouter(tags=["Locations"])

@router.post("/create", response_model=ApiResponse[LocationOut])
def create(payload: LocationCreate, db: Session = Depends(get_db)):
    location = crud.create_location(db, payload)
    return {
        "status" : status.HTTP_200_OK,
        "message": "Location created successfully",
        "data"   : location
    }

@router.get("/list", response_model = ApiResponse[PaginatedResponse[LocationOut]])
def get_locations(db: Session = Depends(get_db), page: int = Query(1, ge=1), limit: int = Query(10, le=50),):
    total, locations = crud.get_locations(db, page=page, limit=limit)
    if not locations:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Locations not found")
    return {
        "status" : status.HTTP_200_OK,
        "message": "Locations fetched successfully",
        "data": {
            "page": page,
            "limit": limit,
            "total": total,
            "items": [crud.map_location_out(loc) for loc in locations]
        }
    }

@router.get("/get/{location_id}", response_model = ApiResponse[LocationOut])
def get_location_by_id(location_id: int, db: Session = Depends(get_db)):
    location = crud.get_location_by_id(db, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return {
        "status" : status.HTTP_200_OK,
        "message": "Location fetched successfully",
        "data"   : location
    }

@router.put("/update/{location_id}", response_model=ApiResponse[LocationOut])
def update_location(location_id: int, payload: LocationUpdate, db: Session = Depends(get_db)):
    location = crud.update_location(db, location_id, payload)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return {
        "status" : status.HTTP_200_OK,
        "message": "Location Updated successfully",
        "data"   : location
    }

@router.delete("/delete/{location_id}", response_model=ApiResponse[LocationOut])
def delete_location(location_id: int, db: Session = Depends(get_db)):
    data = crud.delete_location(db, location_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return {
        "status" : status.HTTP_200_OK,
        "message": "Location Deleted successfully",
        "data"   : data
    }
@router.get("/json/countries", response_model=ApiResponse[List[JSONCountryResponse]])
def get_json_countries(
    id    : int | None = None,
    search: str | None = None, 
):
    countries = crud.get_json_countries()
    if not countries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Countries not found"
        )

    if id is not None:
        countries = [
            c for c in countries
            if c.get("id") == id
        ]

    elif search:
        s = search.strip().lower()
        countries = [
            c for c in countries
            if c.get("name", "").lower().startswith(s)
            or c.get("iso3", "").lower().startswith(s)
        ]

    return {
        "status": status.HTTP_200_OK,
        "message": "Countries fetched successfully",
        "data": countries
    }


@router.get("/json/states/{country_id}",response_model=ApiResponse[List[JSONStateResponse]])
def get_state_by_country_id(
    country_id : int,
    id         : int | None = None,
    search     : str | None = None
):
    states = crud.get_state_by_country_id(country_id)
    if not states:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="States not found for the given country ID"
        )

    if id is not None:
        states = [
            s for s in states
            if s.get("id") == id
        ]

    elif search:
        s = search.strip().lower()
        states = [
            state for state in states
            if state.get("name", "").lower().startswith(s)
            or state.get("iso2", "").lower().startswith(s)
        ]

    return {
        "status": status.HTTP_200_OK,
        "message": "States fetched successfully",
        "data": states
    }

@router.get("/json/cities/{state_id}",response_model=ApiResponse[List[JSONCityResponse]])
def get_city_by_state_id(
    state_id : int,
    id       : int | None = None,
    search   : str | None = None
):
    cities = crud.get_city_by_state_id(state_id)
    if not cities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cities not found for the given state ID"
        )

    if id is not None:
        cities = [
            c for c in cities
            if c.get("id") == id
        ]

    elif search:
        s = search.strip().lower()
        cities = [
            city for city in cities
            if city.get("name", "").lower().startswith(s)
        ]
    

    return {
        "status": status.HTTP_200_OK,
        "message": "Cities fetched successfully",
        "data": cities
    }
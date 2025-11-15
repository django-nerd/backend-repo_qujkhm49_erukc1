import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Food Delivery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Food Delivery API is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# Utility to convert ObjectId strings safely

def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


# Schemas for request bodies
class RestaurantIn(BaseModel):
    name: str
    cuisine: str
    rating: float = 4.5
    delivery_time_min: int = 30
    image_url: Optional[str] = None


class MenuItemIn(BaseModel):
    restaurant_id: str
    title: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    vegetarian: bool = False


class OrderItemIn(BaseModel):
    menu_item_id: str
    quantity: int = 1


class OrderIn(BaseModel):
    customer_name: str
    address: str
    restaurant_id: str
    items: List[OrderItemIn]


# Endpoints
@app.get("/restaurants")
def list_restaurants():
    docs = get_documents("restaurant")
    for d in docs:
        d["_id"] = str(d["_id"])  # stringify ids
    return docs


@app.post("/restaurants", status_code=201)
def create_restaurant(payload: RestaurantIn):
    rid = create_document("restaurant", payload.model_dump())
    return {"id": rid}


@app.get("/restaurants/{restaurant_id}/menu")
def list_menu(restaurant_id: str):
    docs = get_documents("menuitem", {"restaurant_id": restaurant_id})
    for d in docs:
        d["_id"] = str(d["_id"])  # stringify ids
    return docs


@app.post("/menu", status_code=201)
def create_menu_item(payload: MenuItemIn):
    # ensure restaurant exists
    rest = db["restaurant"].find_one({"_id": to_object_id(payload.restaurant_id)}) if ObjectId.is_valid(payload.restaurant_id) else db["restaurant"].find_one({"_id": payload.restaurant_id})
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    mid = create_document("menuitem", payload.model_dump())
    return {"id": mid}


@app.post("/orders", status_code=201)
def place_order(payload: OrderIn):
    # basic total calculation
    total = 0.0
    for item in payload.items:
        mi = db["menuitem"].find_one({"_id": to_object_id(item.menu_item_id)}) if ObjectId.is_valid(item.menu_item_id) else db["menuitem"].find_one({"_id": item.menu_item_id})
        if not mi:
            raise HTTPException(status_code=404, detail=f"Menu item not found: {item.menu_item_id}")
        total += float(mi.get("price", 0)) * int(item.quantity)

    order_doc = {
        "customer_name": payload.customer_name,
        "address": payload.address,
        "restaurant_id": payload.restaurant_id,
        "items": [i.model_dump() for i in payload.items],
        "total": round(total, 2),
        "status": "placed",
    }
    oid = create_document("order", order_doc)
    return {"id": oid, "total": order_doc["total"], "status": order_doc["status"]}


@app.get("/orders")
def list_orders():
    docs = get_documents("order")
    for d in docs:
        d["_id"] = str(d["_id"])  # stringify ids
    return docs


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

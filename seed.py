from app.routers.seed import seed_data


if __name__ == "__main__":
    result = seed_data()
    print(result.get("message", "Seed completed."))
import asyncio
from sqlalchemy import select
from app.models import Base, User, Crop, CropParam, ActiveConfig
from app.auth import get_password_hash


CROPS_DATA = [
    {
        "name": "tomate",
        "display_name": "Tomate",
        "description": "Cultivo de estación cálida, muy común en invernaderos",
        "params": {
            "temp_min": 12.0,
            "temp_max": 30.0,
            "temp_night_min": 13.0,
            "temp_night_max": 16.0,
            "humidity_min": 55.0,
            "humidity_max": 70.0,
            "soil_moisture_min_pct": 40,
            "soil_moisture_max_pct": 70,
            "hysteresis_temp_on": 30.0,
            "hysteresis_temp_off": 27.5,
            "hysteresis_humidity_on": 60.0,
            "hysteresis_humidity_off": 68.0,
            "hysteresis_soil_on": 35,
            "hysteresis_soil_off": 45,
            "source_reference": "FAO - Produccion de tomate bajo invernadero (a1374s); INTA - Produccion de hortalizas bajo cubierta; Tesi en Montero y Anton 1993",
            "source_url": "https://www.fao.org/4/a1374s/a1374s.pdf",
        }
    },
    {
        "name": "pimiento",
        "display_name": "Pimiento / Chile",
        "description": "Cultivo de estación cálida, sensible a temperaturas bajas",
        "params": {
            "temp_min": 12.0,
            "temp_max": 32.0,
            "temp_night_min": 16.0,
            "temp_night_max": 18.0,
            "humidity_min": 65.0,
            "humidity_max": 75.0,
            "soil_moisture_min_pct": 40,
            "soil_moisture_max_pct": 70,
            "hysteresis_temp_on": 30.0,
            "hysteresis_temp_off": 27.5,
            "hysteresis_humidity_on": 65.0,
            "hysteresis_humidity_off": 72.0,
            "hysteresis_soil_on": 35,
            "hysteresis_soil_off": 45,
            "source_reference": "FAO - Manual de produccion de pimiento; INTA - Temperaturas optimas; Tesi 1969",
            "source_url": "https://www.fao.org/4/i3359s/i3359s.pdf",
        }
    },
    {
        "name": "pepino",
        "display_name": "Pepino",
        "description": "Cultivo de estación cálida, requiere alta humedad",
        "params": {
            "temp_min": 14.0,
            "temp_max": 30.0,
            "temp_night_min": 18.0,
            "temp_night_max": 20.0,
            "humidity_min": 70.0,
            "humidity_max": 85.0,
            "soil_moisture_min_pct": 50,
            "soil_moisture_max_pct": 80,
            "hysteresis_temp_on": 30.0,
            "hysteresis_temp_off": 27.5,
            "hysteresis_humidity_on": 70.0,
            "hysteresis_humidity_off": 80.0,
            "hysteresis_soil_on": 45,
            "hysteresis_soil_off": 55,
            "source_reference": "UTADEO - Manual de produccion de pepino bajo invernadero; FAO Kc values",
            "source_url": "https://www.utadeo.edu.co/sites/tadeo/files/node/wysiwyg/pub_54_manual_de_produccion_de_pepino.pdf",
        }
    },
    {
        "name": "melon",
        "display_name": "Melón",
        "description": "Cultivo de estación cálida, tolera calor intenso",
        "params": {
            "temp_min": 13.0,
            "temp_max": 35.0,
            "temp_night_min": 18.0,
            "temp_night_max": 21.0,
            "humidity_min": 50.0,
            "humidity_max": 70.0,
            "soil_moisture_min_pct": 40,
            "soil_moisture_max_pct": 70,
            "hysteresis_temp_on": 32.0,
            "hysteresis_temp_off": 29.0,
            "hysteresis_humidity_on": 55.0,
            "hysteresis_humidity_off": 68.0,
            "hysteresis_soil_on": 35,
            "hysteresis_soil_off": 45,
            "source_reference": "INTA - Produccion de hortalizas bajo cubierta; Montero y Anton 1993",
            "source_url": "https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/17134/INTA_CRPatagoniaNorte_EEAAltoValle_Iglesias_NB_Producci%C3%B3n_hortalizas_bajo_cubierta.pdf",
        }
    },
    {
        "name": "sandia",
        "display_name": "Sandía",
        "description": "Cultivo de estación muy cálida, óptimas >21°C",
        "params": {
            "temp_min": 15.0,
            "temp_max": 38.0,
            "temp_night_min": 20.0,
            "temp_night_max": 24.0,
            "humidity_min": 50.0,
            "humidity_max": 70.0,
            "soil_moisture_min_pct": 40,
            "soil_moisture_max_pct": 70,
            "hysteresis_temp_on": 33.0,
            "hysteresis_temp_off": 30.0,
            "hysteresis_humidity_on": 55.0,
            "hysteresis_humidity_off": 68.0,
            "hysteresis_soil_on": 35,
            "hysteresis_soil_off": 45,
            "source_reference": "INTA - Hortalizas estacion calida Grupo E (berenjena, sandia); FAO",
            "source_url": "https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/17134/INTA_CRPatagoniaNorte_EEAAltoValle_Iglesias_NB_Producci%C3%B3n_hortalizas_bajo_cubierta.pdf",
        }
    },
    {
        "name": "berenjena",
        "display_name": "Berenjena",
        "description": "Cultivo de estación muy cálida, óptimas >21°C",
        "params": {
            "temp_min": 15.0,
            "temp_max": 35.0,
            "temp_night_min": 15.0,
            "temp_night_max": 18.0,
            "humidity_min": 60.0,
            "humidity_max": 75.0,
            "soil_moisture_min_pct": 45,
            "soil_moisture_max_pct": 75,
            "hysteresis_temp_on": 32.0,
            "hysteresis_temp_off": 29.0,
            "hysteresis_humidity_on": 65.0,
            "hysteresis_humidity_off": 72.0,
            "hysteresis_soil_on": 40,
            "hysteresis_soil_off": 50,
            "source_reference": "INTA - Hortalizas estacion calida Grupo E; FAO",
            "source_url": "https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/17134/INTA_CRPatagoniaNorte_EEAAltoValle_Iglesias_NB_Producci%C3%B3n_hortalizas_bajo_cubierta.pdf",
        }
    },
    {
        "name": "calabacin",
        "display_name": "Calabacín / Zapallito",
        "description": "Cultivo de estación cálida, crecimiento rápido",
        "params": {
            "temp_min": 12.0,
            "temp_max": 30.0,
            "temp_night_min": 15.0,
            "temp_night_max": 18.0,
            "humidity_min": 60.0,
            "humidity_max": 80.0,
            "soil_moisture_min_pct": 45,
            "soil_moisture_max_pct": 75,
            "hysteresis_temp_on": 30.0,
            "hysteresis_temp_off": 27.5,
            "hysteresis_humidity_on": 65.0,
            "hysteresis_humidity_off": 75.0,
            "hysteresis_soil_on": 40,
            "hysteresis_soil_off": 50,
            "source_reference": "INTA - Hortalizas estacion calida Grupo D; Tesi 1969",
            "source_url": "https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/17134/INTA_CRPatagoniaNorte_EEAAltoValle_Iglesias_NB_Producci%C3%B3n_hortalizas_bajo_cubierta.pdf",
        }
    },
    {
        "name": "frijol",
        "display_name": "Frijol / Poroto",
        "description": "Cultivo de estación cálida, trepador",
        "params": {
            "temp_min": 12.0,
            "temp_max": 30.0,
            "temp_night_min": 16.0,
            "temp_night_max": 18.0,
            "humidity_min": 55.0,
            "humidity_max": 75.0,
            "soil_moisture_min_pct": 40,
            "soil_moisture_max_pct": 70,
            "hysteresis_temp_on": 30.0,
            "hysteresis_temp_off": 27.5,
            "hysteresis_humidity_on": 60.0,
            "hysteresis_humidity_off": 70.0,
            "hysteresis_soil_on": 35,
            "hysteresis_soil_off": 45,
            "source_reference": "INTA - Hortalizas estacion calida Grupo D (poroto chaucha); FAO",
            "source_url": "https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/17134/INTA_CRPatagoniaNorte_EEAAltoValle_Iglesias_NB_Producci%C3%B3n_hortalizas_bajo_cubierta.pdf",
        }
    },
    {
        "name": "maiz_dulce",
        "display_name": "Maíz Dulce",
        "description": "Cultivo de estación cálida, requiere espacio",
        "params": {
            "temp_min": 12.0,
            "temp_max": 32.0,
            "temp_night_min": 15.0,
            "temp_night_max": 20.0,
            "humidity_min": 55.0,
            "humidity_max": 75.0,
            "soil_moisture_min_pct": 45,
            "soil_moisture_max_pct": 75,
            "hysteresis_temp_on": 31.0,
            "hysteresis_temp_off": 28.0,
            "hysteresis_humidity_on": 60.0,
            "hysteresis_humidity_off": 70.0,
            "hysteresis_soil_on": 40,
            "hysteresis_soil_off": 50,
            "source_reference": "FAO - Produccion de maiz; INTA",
            "source_url": "https://www.fao.org/3/x0490e/x0490e00.htm",
        }
    },
    {
        "name": "cilantro",
        "display_name": "Cilantro",
        "description": "Hierba aromática, tolera algo de calor",
        "params": {
            "temp_min": 10.0,
            "temp_max": 28.0,
            "temp_night_min": 12.0,
            "temp_night_max": 18.0,
            "humidity_min": 55.0,
            "humidity_max": 75.0,
            "soil_moisture_min_pct": 45,
            "soil_moisture_max_pct": 75,
            "hysteresis_temp_on": 28.0,
            "hysteresis_temp_off": 25.5,
            "hysteresis_humidity_on": 60.0,
            "hysteresis_humidity_off": 70.0,
            "hysteresis_soil_on": 40,
            "hysteresis_soil_off": 50,
            "source_reference": "PortalFruticola - Temperaturas cardinales hortalizas; INIA lechuga como referencia similar",
            "source_url": "https://www.portalfruticola.com/noticias/2023/02/08/produccion-de-hortalizas-en-invernadero/",
        }
    },
    {
        "name": "lechuga",
        "display_name": "Lechuga (difícil en calor)",
        "description": "Cultivo de estación fría - DIFÍCIL en Santa Lucía (31.5°C máx). Requiere variedades termotolerantes y sombreo",
        "params": {
            "temp_min": 6.0,
            "temp_max": 24.0,
            "temp_night_min": 10.0,
            "temp_night_max": 15.0,
            "humidity_min": 60.0,
            "humidity_max": 80.0,
            "soil_moisture_min_pct": 50,
            "soil_moisture_max_pct": 80,
            "hysteresis_temp_on": 24.0,
            "hysteresis_temp_off": 22.0,
            "hysteresis_humidity_on": 65.0,
            "hysteresis_humidity_off": 75.0,
            "hysteresis_soil_on": 45,
            "hysteresis_soil_off": 55,
            "source_reference": "INIA - Manual de produccion de lechuga; FAO - Temperaturas optimas 15-18°C día, 10-15°C noche. ADVERTENCIA: Clima Santa Lucía supera 30°C frecuente.",
            "source_url": "https://studylib.es/doc/9173081/inia-libro-lechuga",
        }
    },
    {
        "name": "fresa",
        "display_name": "Fresa (difícil en calor)",
        "description": "Cultivo de estación fría/templada - DIFÍCIL en Santa Lucía. Requiere <25°C día, noches frescas. Posible solo en época fresca (nov-feb) con sombreo",
        "params": {
            "temp_min": 8.0,
            "temp_max": 25.0,
            "temp_night_min": 8.0,
            "temp_night_max": 13.0,
            "humidity_min": 60.0,
            "humidity_max": 80.0,
            "soil_moisture_min_pct": 50,
            "soil_moisture_max_pct": 80,
            "hysteresis_temp_on": 25.0,
            "hysteresis_temp_off": 23.0,
            "hysteresis_humidity_on": 65.0,
            "hysteresis_humidity_off": 75.0,
            "hysteresis_soil_on": 45,
            "hysteresis_soil_off": 55,
            "source_reference": "FAO - Produccion de fresa; Requiere 15-25°C día, 8-13°C noche. Santa Lucía media 25.7°C.",
            "source_url": "https://www.fao.org/3/a1374s/a1374s.pdf",
        }
    },
]


DEFAULT_CONFIG = {
    "version": 1,
    "crop": "tomate",
    "hysteresis": {
        "temp": {"on_above": 30.0, "off_below": 27.5},
        "humidity": {"on_below": 60.0, "off_above": 68.0},
        "soil": {"on_below_pct": 35, "off_above_pct": 45},
    },
    "irrigation": {"enabled": False},
    "safety": {
        "max_on_seconds": {
            "fan": 7200,
            "humidifier": 7200,
            "pump": 900,
        }
    },
}


async def ensure_seed_data(session_factory=None):
    """Idempotently create default users, crops, params and active config.

    Safe to call on every startup. Accepts an optional async session factory
    so callers (e.g. the API lifespan) reuse the app's engine.
    """
    if session_factory is None:
        from app.database import AsyncSessionLocal
        session_factory = AsyncSessionLocal

    async with session_factory() as db:
        admin_result = await db.execute(select(User).where(User.username == "admin"))
        admin = admin_result.scalar_one_or_none()
        if not admin:
            admin = User(
                username="admin",
                email="admin@greenhouse.local",
                hashed_password=get_password_hash("admin123"),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            await db.flush()

        viewer_result = await db.execute(select(User).where(User.username == "viewer"))
        if not viewer_result.scalar_one_or_none():
            db.add(User(
                username="viewer",
                email="viewer@greenhouse.local",
                hashed_password=get_password_hash("viewer123"),
                role="viewer",
                is_active=True,
            ))

        first_crop_id = None
        for crop_data in CROPS_DATA:
            existing = await db.execute(select(Crop).where(Crop.name == crop_data["name"]))
            crop = existing.scalar_one_or_none()
            if not crop:
                crop = Crop(
                    name=crop_data["name"],
                    display_name=crop_data["display_name"],
                    description=crop_data["description"],
                    is_active=True,
                )
                db.add(crop)
                await db.flush()
                db.add(CropParam(crop_id=crop.id, **crop_data["params"]))
            if first_crop_id is None:
                first_crop_id = crop.id

        active_result = await db.execute(select(ActiveConfig).where(ActiveConfig.is_active == True))
        if not active_result.scalar_one_or_none():
            db.add(ActiveConfig(
                config_json=DEFAULT_CONFIG,
                version=1,
                crop_id=first_crop_id,
                applied_by=admin.id,
                esp32_confirmed=False,
            ))

        await db.commit()


async def seed_database():
    from app.database import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_seed_data()
    print("Database seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())
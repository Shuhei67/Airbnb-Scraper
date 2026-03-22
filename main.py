import requests
from pathlib import Path
import logging
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


FILEPATH = Path(__file__).parent / "airbnb.html"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)

# Construit l'URL de recherche en fonction des paramètres d'entrée :
def build_url(city: str, checkin: str, checkout: str, adults: int) -> str:
    city_formatted = city.replace(" ", "--") # "New York" → "New--York"
    return f"https://www.airbnb.fr/s/{city_formatted}/homes?refinement_paths%5B%5D=%2Fhomes&checkin={checkin}&checkout={checkout}&date_picker_type=calendar&adults={adults}&guests={adults}&search_type=AUTOSUGGEST"

# Récupère 5 pages de résultats de recherche Airbnb et retourne une liste de leur contenu HTML :
def fetch_content(url: str, from_disk: bool = False) -> list:

    if from_disk and FILEPATH.exists():
        return read_from_file()

    try:
        print(50 * "-")
        print(50 * "-")
        print("🚀 Lancement du scraping, veuillez patienter...")
        logger.debug(f"Récupération du contenu de l'URL : {url}")
        html_pages = [] # Liste qui stockera html de chaque page
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)

            for i in range(5): # On va scraper les 5 premières pages
                page.wait_for_selector("[data-testid='card-container']")
                html_pages.append(page.content()) # On ajoute le contenu HTML à la liste
                print(f"Page {i+1} récupérée.")
                if i < 4:
                    print(f"Récupuration de la page {i + 2} sur 5 en cours ...")
                    page.wait_for_timeout(4000) # Attendre 4s avant de charger la page suivante
                    page.get_by_role("link", name="Suivant").click() # Cliquer sur le bouton "Suivant" pour charger la page suivante
            print(50 * "-")
            print("Analyse terminée !")
            browser.close()

        return html_pages  # on retourne la liste de 5 HTML
    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout : les annonces n'ont pas chargé : {e}")
        raise e
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du contenu : {e}")
        raise e
 

# Traite le contenu HTML pour extraire le prix moyen :
def get_average_price(html_pages: list, max_price: int) -> int:
    prices = []
    excluded = 0

    for html in html_pages:  # On vient boucler sur chaque page
        soup = BeautifulSoup(html, "html.parser")
        divs = soup.find_all("div", {"data-testid": "card-container"})
        for div in divs:
            price_div = div.find("span", class_="sjwpj0z") or div.find("span", class_="u174bpcy")
            if not price_div:
                logger.warning(f"Pas réussi à trouver le prix de la div {div}")
                continue
            price = re.sub(r"\D", "", price_div.text)
            if price.isdigit():
                if int(price) <= max_price:
                    prices.append(int(price))
                else:
                    excluded += 1
            else:
                logger.warning(f"Le prix trouvé n'est pas un nombre : {price}")

    print(f"Nombre d'annonces analysées : {len(prices)}")
    print(f"Prix le moins cher : {min(prices)}€")
    print(f"Prix le plus cher : {max(prices)}€")
    print(f"Annonces exclues : {excluded}")

    return round(sum(prices) / len(prices)) if prices else 0


# Écrit le contenu dans un fichier :
def write_to_file(content: str) -> bool:
    logger.debug(f"Écriture du contenu dans le fichier")
    with open(FILEPATH, "w", encoding="utf-8") as f:
        f.write(content)

    return FILEPATH.exists()
    # Vérifie si le fichier a été créé avec succès


# Lit le contenu du fichier :
def read_from_file() -> str:
    logger.debug(f"Lecture du contenu du fichier")
    with open(FILEPATH, "r", encoding="utf-8") as f:
        return f.read()



if __name__ == "__main__":
    print(50 * "-")
    city = input("Ville : ")
    checkin = input("Date d'arrivée (YYYY-MM-DD) : ")
    checkout = input("Date de départ (YYYY-MM-DD) : ")
    adults = int(input("Nombre de personnes : "))
    max_price = int(input("Budget total maximum pour le mois : "))

    url = build_url(city=city, checkin=checkin, checkout=checkout, adults=adults)
    content = fetch_content(url=url, from_disk=False) # En mettant false il va sur internet
    average_price = get_average_price(html_pages=content, max_price=max_price)
    print(50 * "-")
    print(f"Le prix moyen des annonces est de {average_price}€")
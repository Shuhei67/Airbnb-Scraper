import requests
from pathlib import Path
import logging
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import quote # Transforme caractères spéciaux en URL safe
from datetime import datetime

FILEPATH = Path(__file__).parent / "airbnb.html"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)


# Récupère les infos de l'utilisateur (ville, dates, nombre de personnes, budget) et valide les infos :
def get_user_inputs() -> tuple:

    print(50 * "-")
    while True:
        city = input("Ville : ").strip()
        if city:
            break
        print("❌ Veuillez saisir une ville valide.")
    while True:
        checkin = input("Date d'arrivée (YYYY-MM-DD) : ").strip()
        try:
            checkin_date = datetime.strptime(checkin, "%Y-%m-%d")
            break
        except ValueError:
            print("❌ Format de date invalide, veuillez utilisez YYYY-MM-DD .")
    while True:
        checkout = input("Date de départ (YYYY-MM-DD) : ").strip()
        try:
            checkout_date = datetime.strptime(checkout, "%Y-%m-%d")
            if checkout_date <= checkin_date:
                print("❌ La date de départ doit être après la date d'arrivée.")
            else:
                break
        except ValueError:
            print("❌ Format de date invalide, veuillez utilisez YYYY-MM-DD .")
    while True:
        try:
            adults = int(input("Nombre de personnes : "))
            if adults > 0:
                break
            print("❌ Le nombre de personnes doit être supérieur à 0.")
        except ValueError:
            print("❌ Veuillez entrer un nombre entier.")
    while True:
        try:
            max_price = int(input("Budget total maximum : "))
            if max_price > 0:
                break
            print("❌ Le budget doit être supérieur à 0.")
        except ValueError:
            print("❌ Veuillez entrer un nombre entier.")

    return city, checkin, checkout, adults, max_price


# Construit l'URL de recherche en fonction des paramètres d'entrée :
def build_url(city: str, checkin: str, checkout: str, adults: int) -> str:
    city_formatted = quote(city.replace(" ", "--")) # "New York" → "New--York"
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)

            for i in range(5): # On va scraper les 5 premières pages
                page.wait_for_selector("[data-testid='card-container']")
                html_pages.append(page.content()) # On ajoute le contenu HTML à la liste
                print(f"Page {i+1} récupérée.")
                if i < 4:
                    try:
                        suivant = page.wait_for_selector("a[aria-label='Suivant']", timeout = 3000) # Vérifie si le bouton Suivant existe
                        print(f"Récupuration de la page {i + 2} sur 5 en cours ...")
                        page.wait_for_timeout(2500) # Attendre 2.5s avant de charger la page suivante
                        suivant.click() # Cliquer sur le bouton "Suivant" pour charger la page suivante
                    except:
                        print("Pas de page suivante trouvée, arrêt du scraping.")
                        break
            print(50 * "-")
            print("Analyse terminée !")
            print(50 * "-")
            browser.close()

        return html_pages  # on retourne la liste de 5 HTML
    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout : les annonces n'ont pas chargé : {e}")
        raise e
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du contenu : {e}")
        raise e
 

# Traite le contenu HTML pour extraire les informations sur les annonces (prix, liens) et affiche les statistiques :
def analyze_listings(html_pages: list, max_price: int) -> None:
    prices = []
    excluded = 0
    links = []

    for html in html_pages:  # On vient boucler sur chaque page
        soup = BeautifulSoup(html, "html.parser")
        divs = soup.find_all("div", {"data-testid": "card-container"})
        for div in divs:
            link = div.find("a", href=True)
            price_div = div.find("span", class_="sjwpj0z") or div.find("span", class_="u174bpcy")
            if not price_div:
                logger.warning(f"Pas réussi à trouver le prix de la div {div}")
                continue
            price = re.sub(r"\D", "", price_div.text)
            if price.isdigit():
                if int(price) <= max_price:
                    prices.append(int(price))
                    if link:
                        href = link["href"].split("?")[0]  # On garde uniquement la partie avant le "?", ça rend plus "jolie" dans les résultats
                        links.append((int(price), f"https://www.airbnb.fr{href}"))
                else:
                    excluded += 1

    print(f"Nombre d'annonces analysées : {len(prices)}")
    print(f"Annonces exclues (hors budget) : {excluded}")
    if not prices:
        print("Aucune annonce dans votre budget !")
        return 0
    print(f"Prix le moins cher : {min(prices)}€")
    print(f"Prix le plus cher : {max(prices)}€")
    average = round(sum(prices) / len(prices)) if prices else 0
    print(f"Le prix moyen des annonces est de {average} euros")
    print(50 * "-")
    print(50 * "-")
    print("Voici dans l'ordre croissant les annonces dans votre budget :")
    print(50 * "-")
    for price, url_link in sorted(links):  # ← trié du moins cher au plus cher
        print(f"- {price}€ ---> {url_link}")


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
    city, checkin, checkout, adults, max_price = get_user_inputs()
    url = build_url(city=city, checkin=checkin, checkout=checkout, adults=adults)
    content = fetch_content(url=url, from_disk=False) # En mettant false il va sur internet
    analyze_listings(html_pages=content, max_price=max_price)
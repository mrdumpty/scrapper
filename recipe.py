from bs4 import BeautifulSoup
import requests
import re
import datetime
from enum import Enum
from decimal import Decimal
from catalogs import glasses, components, measurements


class UnknownMarker(Exception):
    pass


class Size(Enum):
    SHOOTER = 1
    SHORT = 2
    LONG = 3


class Temperature(Enum):
    FROZEN = 'f'
    COLD = 'c'
    ROOM = 'n'
    WARM = 'h'


class ImportedRecipe:

    def __init__(self):
        self.node = None
        self.russian_name = None
        self.english_name = None
        self.date_added = None
        self.total_rating = 0
        self.votes = 0
        self.ingredients = dict()
        self.glasses = list()
        self.size = Size.SHOOTER
        self.instruction = ''
        self.temperature = Temperature.ROOM
        self.burning = False
        self.layered = False
        self.julep = False

    def scrap(self, url):
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")

        # Recipe russian and english name
        header = soup.find('h1', text=True)
        text = header.get_text()
        regexp_name = re.compile(r'^([\s\S]+)\(([\s\S]+)\)')
        rus_name = re.match(regexp_name, text).group(1).strip()
        eng_name = re.match(regexp_name, text).group(2)
        self.russian_name = rus_name
        self.english_name = eng_name

        # Old ID
        old_id = soup.find('input', {'name': 'content_id'}).get('value')
        self.node = int(old_id)

        # Date Added
        raw_date = soup.find('span', {'class': 'date'}).get_text()
        date_regexp = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')
        date_digits = re.search(date_regexp, raw_date).group(3, 2, 1)
        year = int(date_digits[0])
        month = int(date_digits[1])
        day = int(date_digits[2])
        self.date_added = datetime.date(year, month, day)

        # Rating
        avg_rating = 0
        average_rating = soup.find('span', {'class': 'average-rating'})

        if average_rating:
            avg_rating = Decimal(average_rating.findChildren('span', recursive=False)[0].get_text())
        total_votes = soup.find('span', {'class': 'total-votes'})
        if total_votes:
            self.votes = int(total_votes.findChildren('span', recursive=False)[0].get_text())

        if avg_rating > 5:
            avg_rating = 5
        self.total_rating = round(self.votes * avg_rating, 0)

        # Instruction
        instruction_tag = soup.find('div', {'class': 'instructions'})
        for img in instruction_tag.find_all('img'):
            img.decompose()
        instruction_paragraphs = instruction_tag.findChildren('p', recursive=True)
        for paragraph in instruction_paragraphs:
            self.instruction += paragraph.prettify()

        # Ingredients
        ingredients = soup.find_all('span', {'class': 'ingredient'})
        ingred_list = list()
        for ingredient_raw in ingredients:
            ingred = ingredient_raw.get_text()
            if ingred not in components:
                raise UnknownMarker(ingred)
            ingred_list.append(ingred)

        ingred_block = soup.find('fieldset', {'class': 'fieldgroup group-ingred'})
        ingred_text = ingred_block.get_text()

        for ingredient in ingred_list:
            regexp_ingred = re.compile(r'^.*{} - ([0-9]+) ([а-я]+),'.format(ingredient.replace("(", '\\(').
                                                                            replace(")", '\\)')))

            try:
                value = re.search(regexp_ingred, ingred_text).group(1)
                measure = re.search(regexp_ingred, ingred_text).group(2)
            except AttributeError:
                value = None
                measure = None

            if measure:
                if measure not in measurements:
                    raise UnknownMarker(measure)
                component_id = components.get(ingredient)
                measure_id = measurements.get(measure)
                self.ingredients[component_id] = [value, measure_id]

        legends = soup.find_all('legend')

        type_legend = legends[1]
        cocktail_type_regex = re.compile(r'(шутер|шот|лонг)')
        cocktail_type = re.search(cocktail_type_regex, type_legend.get_text()).group(1)
        if cocktail_type == 'шутер':
            self.size = Size.SHOOTER
        elif cocktail_type == 'шот':
            self.size = Size.SHORT
        else:
            self.size = Size.LONG

        serving_fieldset = soup.find_all('fieldset', {'class': 'fieldgroup group-additional'})[1]
        serving_images = serving_fieldset.findChildren('img', recursive=True)
        for image in serving_images:
            marker = image.get('alt')
            if marker == 'Со льдом' or marker == 'Безо льда':
                self.temperature = Temperature.COLD
                continue
            if marker == 'Замороженный':
                self.temperature = Temperature.FROZEN
                continue
            if marker == 'Горячий':
                self.temperature = Temperature.WARM
                continue
            if marker == 'С зеленью':
                self.julep = True
                continue
            if marker == 'Слоистые':
                self.layered = True
                continue
            if marker == 'Горящие':
                self.burning = True
                continue
            if marker in glasses:
                self.glasses.append(glasses[marker])
                continue
            print(marker)
            raise UnknownMarker(marker)

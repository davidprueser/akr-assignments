import requests
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace, RDF, RDFS, URIRef, Literal, OWL

ontology_path = "Rehab.rdf"
g = Graph()
g.parse(ontology_path)

REHAB = Namespace("http://www.semanticweb.org/dprueser/ontologies/2025/4/rehab-exercises#")
g.bind("rehab", REHAB)

exercise_class = REHAB.Exercise

url = "https://www.rehabhero.ca/back"
response = requests.get(url)
soup = BeautifulSoup(response.content, "html.parser")

# All classes
category_spans = soup.select("span.sqsrte-text-color--accent")
black_spans = soup.select("span.sqsrte-text-color--black")

all_texts = set()

for span in category_spans + black_spans:
    text = span.get_text(strip=True)
    if text:
        all_texts.add(text)

categories = {text for text in all_texts if text}

for category in categories:
    category_uri = REHAB[category.replace(" ", "_")]
    g.add((category_uri, RDF.type, OWL.Class))
    g.add((category_uri, RDFS.subClassOf, exercise_class))
    g.add((category_uri, RDFS.label, Literal(category)))


# We added Strengthening as a subclass of Exercise manually since there is a mistake in the original code on the website
strengthening_uri = REHAB["Strengthening"]
g.add((strengthening_uri, RDF.type, OWL.Class))
g.add((strengthening_uri, RDFS.subClassOf, exercise_class))
g.add((strengthening_uri, RDFS.label, Literal("Strengthening")))

g.serialize(destination="Scraped_Rehab_2.rdf", format="xml")
print("Updated ontology saved as 'Scraped_Rehab.rdf'")

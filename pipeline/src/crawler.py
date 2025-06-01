import requests
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace, URIRef, RDFS


# 1) SCRAPE RehabHero “Back” PAGE FOR CATEGORIES
def extract_categories(url="https://www.rehabhero.ca/back"):
    """
    Fetches the given RehabHero page and returns a list of category names,
    e.g. ["Stretches", "Strengthening", ...].
    """
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # As of mid-2025, RehabHero’s “Back” page
    # puts its category‐buttons under a div.ExerciseTypesFilter.
    # Each <a> inside that div has the visible text we want.
    #
    # If the site’s markup changes, you may need to inspect
    # the HTML and adjust this selector:
    container = soup.select_one("div.ExerciseTypesFilter")
    if not container:
        raise RuntimeError("Could not find the category filter container on the page.")

    categories = []
    for a in container.select("a"):
        text = a.get_text(strip=True)
        if text:
            categories.append(text)
    return categories


# 2) LOAD EXISTING ONTOLOGY AND ADD SUBCLASSES
def add_categories_as_subclasses(ontology_path, output_path, categories):
    """
    - Loads the RDF/OWL file at ontology_path.
    - Finds the IRI of the class named 'Exercise' (assumes it exists).
    - For each category in 'categories', creates a new class with that label
      (URI: <namespace>#<CategoryNameWithNoSpaces>), asserts
        newClass rdf:type owl:Class ;
                 rdfs:subClassOf Exercise .
      and also adds rdfs:label for human readability.
    - Serializes the updated graph to output_path (Turtle).
    """
    g = Graph()
    g.parse(ontology_path, format="xml")  # assuming Rehabilitation ontology is RDF/XML

    # 2.1) Identify the namespace and the Exercise class IRI
    # We search for any resource whose local‐name (fragment) is "Exercise"
    exercise_iri = None
    for s in g.subjects(predicate=RDFS.subClassOf, object=None):
        # this loops too many triples; instead search all URIs ending with "#Exercise" or "/Exercise"
        pass

    # A more direct approach: iterate over all class resources and look for “Exercise”
    for cls in g.subjects(predicate=None, object=None):
        if isinstance(cls, URIRef) and cls.split("#")[-1].lower() == "exercise":
            exercise_iri = cls
            break
    if exercise_iri is None:
        raise RuntimeError("Could not find a class named 'Exercise' in the ontology.")

    # Derive the base namespace from exercise_iri
    # e.g. if exercise_iri = http://example.org/rehab#Exercise
    # then NS = Namespace("http://example.org/rehab#")
    base_ns_str = exercise_iri.toPython().rsplit("#", 1)[0] + "#"
    NS = Namespace(base_ns_str)

    # 2.2) For each scraped category, create a new URI and declare it
    # as an owl:Class rdfs:subClassOf Exercise, with rdfs:label
    # (We’ll assume these new classes do not conflict with existing ones.)
    for cat in categories:
        # form a safe fragment (remove spaces, punctuation; here just remove spaces)
        frag = "".join(cat.split())  # e.g. “Strengthening” → “Strengthening”
        new_cls = NS[frag]

        # Add triples:
        g.add((new_cls, RDFS.subClassOf, exercise_iri))
        g.add((new_cls, RDFS.label, URIRef(frag)))  # if you want a literal label:
        # Actually, we want a literal label:
        from rdflib import Literal

        g.remove((new_cls, RDFS.label, None))
        g.add((new_cls, RDFS.label, Literal(cat)))

    # 3) Write out the augmented ontology
    g.serialize(destination=output_path, format="turtle")


if __name__ == "__main__":
    # 1) Scrape categories
    categories = extract_categories()

    # 2) Load your ontology (Rehab.rdf) and add subclasses
    #    Write the result to a new file so you keep your original unchanged.
    input_ontology = "Rehab.rdf"
    output_ontology = "Rehab_with_categories.rdf"

    add_categories_as_subclasses(input_ontology, output_ontology, categories)

    print(
        f"Added {len(categories)} subclasses to 'Exercise'.\n"
        f"Updated ontology saved as '{output_ontology}'."
    )

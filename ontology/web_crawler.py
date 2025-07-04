"""
This module defines a web crawler that scrapes exercise categories and their details from a specified URL,
and updates an RDF ontology with the scraped data.

Date: 04.07.2025
"""

import requests
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace, RDF, RDFS, URIRef, Literal, OWL


class RehabOntologyCrawler:
    def __init__(self, ontology_path: str, namespace_uri: str):
        self.ontology_path = ontology_path
        self.graph = Graph()
        # self.REHAB = Namespace("http://www.semanticweb.org/dprueser/ontologies/2025/4/rehab-exercises#")
        self.REHAB = Namespace(namespace_uri)

        self.graph.bind("rehab", self.REHAB)
        self.exercise_class = self.REHAB.Exercise
        self._soup = None

    def load_ontology(self):
        self.graph.parse(self.ontology_path)

    def fetch_page(self, url: str):
        """
        Fetches the content of the given URL and parses it with BeautifulSoup.

        :param url: The URL to fetch.
        """
        response = requests.get(url)
        response.raise_for_status()
        self._soup = BeautifulSoup(response.content, "html.parser")

    def extract_texts(self) -> set[str]:
        """
        Extracts all relevant texts from the marked <span> elements in the fetched page content.

        :return: A set of unique texts extracted from the page.
        """

        if self._soup is None:
            raise RuntimeError("Page content not fetched. Call fetch_page() first.")
        category_spans = self._soup.select("span.sqsrte-text-color--accent")
        black_spans = self._soup.select("span.sqsrte-text-color--black")
        texts = {
            span.get_text(strip=True)
            for span in category_spans + black_spans
            if span.get_text(strip=True)
        }
        return texts
    
    def add_categories(self, texts: set[str], parent_class: URIRef):
        """
        Adds categories as subclasses of the specified parent class in the ontology.

        :param texts: A set of category names to be added as subclasses.
        :param parent_class: The URIRef of the parent class to which the categories will be added as subclasses.
        """
        for text in texts:
            uri = self.REHAB[text.replace(" ", "_")]
            self.graph.add((uri, RDF.type, OWL.Class))
            self.graph.add((uri, RDFS.subClassOf, parent_class))
            self.graph.add((uri, RDFS.label, Literal(text)))


    def add_strengthening(self, parent_class: URIRef):
        """
        Adds the 'Strengthening' class to the ontology as a subclass of the specified parent class.

        :param parent_class: The URIRef of the parent class to which 'Strengthening' will be added as a subclass.
        """
        uri = self.REHAB["Strengthening"]
        if (uri, RDF.type, OWL.Class) not in self.graph:
            self.graph.add((uri, RDF.type, OWL.Class))
            self.graph.add((uri, RDFS.subClassOf, parent_class))
            self.graph.add((uri, RDFS.label, Literal("Strengthening")))

    def serialize(self, destination: str, fmt: str = "xml"):
        """
        Serializes the RDF graph to the specified destination in the given format.

        :param destination: The file path where the serialized graph will be saved.
        :param fmt: The format in which to serialize the graph (default is 'xml').
        """
        self.graph.serialize(destination=destination, format=fmt)
        print(f"Updated ontology saved as '{destination}'")


if __name__ == "__main__":
    crawler = RehabOntologyCrawler(
        ontology_path="Rehab.rdf",
        namespace_uri="http://www.semanticweb.org/dprueser/ontologies/2025/4/rehab-exercises#"
    )
    crawler.fetch_page("https://www.rehabhero.ca/back")
    texts = crawler.extract_texts()
    parent = crawler.REHAB.Exercise
    crawler.add_categories(texts, parent)
    crawler.add_strengthening(parent)
    crawler.serialize("Scraped_Rehab_2.rdf")
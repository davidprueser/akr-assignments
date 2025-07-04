"""
This module defines a web crawler that scrapes exercise categories and their details from a specified URL,
and updates an RDF ontology with the scraped data.

Date: 04.07.2025
"""

import requests
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace, RDF, RDFS, URIRef, Literal, OWL


class RehabOntologyCrawler:
    """
    Crawler class for incremental scraping of exercise categories and
    updating an RDF ontology with the scraped data.
    """

    def __init__(
        self,
        base_ontology_path: str,
        working_ontology_path: str | None = None,
        namespace_uri: str = "http://www.semanticweb.org/dprueser/ontologies/2025/4/rehab-exercises#",
    ):
        """
        :param base_ontology_path: Path to the original ontology file (.rdf)
        :param working_ontology_path: Target file for updates (default: base path with _updated.rdf)
        :param namespace_uri: URI of the rehab namespace
        """
        self.base_path = base_ontology_path
        self.work_path = working_ontology_path or base_ontology_path.replace(
            ".rdf", "_updated.rdf"
        )
        self.REHAB = Namespace(namespace_uri)
        self.graph = Graph()
        self.graph.bind("rehab", self.REHAB)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.exercise_class = self.REHAB.Exercise
        self._soup = None

        self.graph.bind("rehab", self.REHAB)
        self.exercise_class = self.REHAB.Exercise
        self._soup = None

    def run(self, urls: list[str], destination: str | None = None):
        """
        Orchestrate the full workflow:
        1) Load the ontology,
        2) For each URL: scrape and add categories,
        3) Add 'Strengthening' workaround,
        4) Save the updated graph.

        :param urls: List of page URLs to scrape
        :param destination: Optional output filename for serialization
        """
        # Step 1: Load the ontology
        self.load_ontology()

        # Step 2: Scrape each page and add categories
        for url in urls:
            print(f"Scraping {url}...")
            self.fetch_page(url)
            texts = self.extract_texts()
            self.add_categories(texts, self.exercise_class)

        # Step 3: Add Strengthening workaround
        self.add_strengthening(self.exercise_class)

        # Step 4: Serialize the updated graph
        self.serialize(destination)

    def load_ontology(self):
        """
        Load the original ontology and then, if available,
        the current update file to maintain incremental additions.
        """
        # Load the original ontology
        self.graph.parse(self.base_path, format="xml")
        # Load previous updates if the file exists
        try:
            with open(self.work_path, "rb"):
                self.graph.parse(self.work_path, format="xml")
        except FileNotFoundError:
            pass

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
            if (uri, RDF.type, OWL.Class) in self.graph:
                continue  # Skip if the class already exists
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

    def serialize(self, destination: str | None = None, fmt: str = "xml"):
        """
        Serializes the RDF graph to the specified destination in the given format.

        :param destination: The file path where the serialized graph will be saved.
        :param fmt: The format in which to serialize the graph (default is 'xml').
        """
        target = destination or self.work_path
        self.graph.serialize(destination=target, format=fmt)
        print(f"Updated ontology saved as '{target}'")


if __name__ == "__main__":
    crawler = RehabOntologyCrawler(
        base_ontology_path="Rehab.rdf",
    )
    urls_to_scrape = ["https://www.rehabhero.ca/back", "https://www.rehabhero.ca/neck"]
    crawler.run(urls_to_scrape, destination="Scraped_Rehab_Final.rdf")

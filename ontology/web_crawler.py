"""
This module defines a web crawler that scrapes exercise categories and their details from a specified URL,
and updates an RDF ontology with the scraped data.

Date: 04.07.2025
Last updated: 04.07.2025
"""

import requests
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace, RDF, RDFS, URIRef, Literal, OWL
import re


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
        # Derive default namespace URI for XML serialization
        self.default_ns = namespace_uri.rstrip("#")
        if not self.default_ns.endswith("/"):
            self.default_ns += "/"

        self.graph = Graph()
        # bind namespaces
        self.graph.bind("rehab", self.REHAB)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        # bind default namespace prefix to empty string
        self.graph.namespace_manager.bind("", Namespace(self.default_ns))

        self.exercise_class = self.REHAB.Exercise
        self._soup = None
        # Will hold all definition triples to re-add later
        self._defs: list[tuple[URIRef, URIRef, URIRef]] = (
            []
        )  # Renamed from _property_defs

    def run(
        self,
        urls: list[str],
        category_urls: list[str],
        destination: str | None = None,
    ):
        """
        Orchestrate the full workflow:
        1) Load the ontology,
        2) For each URL: scrape and add categories,
        3) Add 'Strengthening' workaround,
        4) Restore property definitions,
        5) Save the updated graph.

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

        # Step 2.5: Add categories from specific URLs
        for category_url in category_urls:
            print(f"Scraping exercises in {category_url}...")
            self.fetch_page(category_url)
            self.base_url = category_url  # Changed: store base for relative links
            exercises = self.extract_exercise_links()
            # Determine category class from URL or previous category mapping
            seg = category_url.rsplit("/", 1)[-1]  # z.B. "Thoracic+Flexibility"
            kind = seg.split("+")[-1]  # z.B. "Flexibility"

            if kind == "Flexibility":
                cls_name = "Stretches"
            else:
                cls_name = kind.capitalize()
            category_class = self.REHAB[cls_name]

            self.add_exercises(exercises, category_class)

        # Step 3: Add Strengthening workaround
        self.add_strengthening(self.exercise_class)

        # Step 4: Restore property definitions
        self.add_property_definitions()

        # Step 5: Serialize the updated graph
        self.serialize(destination)

    def load_ontology(self):
        """
        Load the original ontology and capture all property definitions
        from ObjectProperty, DatatypeProperty, and AnnotationProperty.
        """
        # Load base ontology
        self.graph.parse(self.base_path, format="xml")

        # Capture all property definitions
        self._capture_properties(OWL.ObjectProperty)
        self._capture_properties(OWL.DatatypeProperty)
        self._capture_properties(OWL.AnnotationProperty)

        # Capture NamedIndividual definitions (e.g., symp, doid)
        self._capture_named_individuals()

        # Load incremental updates if present
        try:
            with open(self.work_path, "rb"):
                self.graph.parse(self.work_path, format="xml")
        except FileNotFoundError:
            pass

    ##### Web Scraping Methods #####

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
            raise RuntimeError("Page not fetched. Call fetch_page() first.")
        spans = self._soup.select(
            "span.sqsrte-text-color--accent, span.sqsrte-text-color--black"
        )
        return {
            span.get_text(strip=True) for span in spans if span.get_text(strip=True)
        }

    ##### Scraping Exercise Methods #####

    # Changed: New method to extract exercise links and titles from a category page
    def extract_exercise_links(self) -> list[tuple[str, str]]:
        """
        Finds all exercise links on a category page.
        Returns a list of tuples (exercise_url, exercise_name).
        """
        if self._soup is None:
            raise RuntimeError("Page not fetched. Call fetch_page() first.")
        links = []
        for a in self._soup.select("a[data-no-animation]"):
            href = a.get("href")
            name = a.get_text(strip=True)
            if href and name:
                full_url = requests.compat.urljoin(self.base_url, href)
                links.append((full_url, name))
        return links

    # Changed: New method to add exercise individuals to the ontology
    def add_exercises(self, exercises: list[tuple[str, str]], category_class: URIRef):
        """
        Adds exercise individuals under the given category class.
        """
        for url, name in exercises:
            # create a URI for the exercise individual
            indiv_uri = self.REHAB[name.replace(" ", "_")]
            # add type and class membership
            self.graph.add((indiv_uri, RDF.type, self.REHAB.Exercise))
            self.graph.add((indiv_uri, RDF.type, category_class))
            self.graph.add((indiv_uri, RDFS.label, Literal(name)))
            # optionally store the source URL
            self.graph.add((indiv_uri, self.REHAB.sourceUrl, Literal(url)))

    ##### Ontology Update Methods #####

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

    ##### Property Annotations and Definitions #####

    def _capture_properties(self, prop_type):
        """
        Helper to capture all triples for a given property type.

        :param prop_type: The RDF type of the property to capture (e.g., OWL.ObjectProperty, OWL.DatatypeProperty).
        """
        for prop in self.graph.subjects(RDF.type, prop_type):
            valid_preds = {RDF.type, RDFS.domain, RDFS.range, RDFS.label, RDFS.comment}
            if prop_type == OWL.ObjectProperty:
                valid_preds.add(OWL.inverseOf)
            for pred, obj in self.graph.predicate_objects(prop):
                if pred in valid_preds:
                    self._defs.append((prop, pred, obj))

    def _capture_named_individuals(self):
        """
        Helper to capture definition triples for all NamedIndividuals and their related_to links.
        """
        for indiv in self.graph.subjects(RDF.type, OWL.NamedIndividual):
            # capture type triple
            self._defs.append((indiv, RDF.type, OWL.NamedIndividual))
            # only keep related_to properties
            for pred, obj in self.graph.predicate_objects(indiv):
                if pred == self.REHAB.related_to:
                    self._defs.append((indiv, pred, obj))

    def add_property_definitions(self):
        """
        Restores all captured ObjectProperty and DatatypeProperty definition triples.
        """
        for s, p, o in self._defs:
            self.graph.add((s, p, o))

    def _replace_property_tag(self, rdf_str: str, type_uri: str, tag: str) -> str:
        pattern = (
            rf'<rdf:Description rdf:about="(?P<about>[^"]+)">\s*'
            rf'<rdf:type rdf:resource="{re.escape(type_uri)}"\s*/>(?P<inner>.*?)'
            rf"</rdf:Description>"
        )
        return re.sub(
            pattern,
            lambda m: f'<{tag} rdf:about="{m.group("about")}">{m.group("inner")}</{tag}>',
            rdf_str,
            flags=re.DOTALL,
        )

    def _add_namespace_declaration(self, rdf_str: str) -> str:
        """
        Adds the default namespace declaration to the RDF/XML string if not present.

        :param rdf_str: The RDF/XML string to process.
        :return: The RDF/XML string with the namespace declaration added.
        """
        return re.sub(
            r"<rdf:RDF",
            f'<rdf:RDF xml:base="{self.default_ns.rstrip("/")}" xmlns="{self.default_ns}"',
            rdf_str,
            count=1,
        )

    def _post_process(self, rdf_str: str) -> str:
        """
        Applies all property tag replacements to the RDF/XML string,
        then inserts blank lines between top-level elements for readability.
        """
        # Convert Description to proper owl tags
        rdf_str = self._add_namespace_declaration(rdf_str)
        rdf_str = self._replace_property_tag(
            rdf_str, OWL.ObjectProperty.toPython(), "owl:ObjectProperty"
        )
        rdf_str = self._replace_property_tag(
            rdf_str, OWL.DatatypeProperty.toPython(), "owl:DatatypeProperty"
        )
        rdf_str = self._replace_property_tag(
            rdf_str, OWL.AnnotationProperty.toPython(), "owl:AnnotationProperty"
        )
        # Insert blank lines after closing tags of top-level elements
        rdf_str = re.sub(r"(</owl:[^>]+>)", r"\1\n", rdf_str)
        rdf_str = re.sub(r"(</rdf:Description>)", r"\1\n", rdf_str)
        return rdf_str

    ##### Serialization #####

    def serialize(self, destination: str | None = None, fmt: str = "xml"):
        """
        Serializes the RDF graph to the specified destination, then post-
        processes the RDF/XML string to convert generic <rdf:Description>
        blocks into proper <owl:*Property> tags.
        """
        target = destination or self.work_path
        rdf_str = self.graph.serialize(format=fmt)
        if isinstance(rdf_str, bytes):
            rdf_str = rdf_str.decode("utf-8")
        rdf_str = self._post_process(rdf_str)
        with open(target, "w", encoding="utf-8") as f:
            f.write(rdf_str)
        print(f"Updated ontology saved as '{target}'")


if __name__ == "__main__":
    crawler = RehabOntologyCrawler(
        base_ontology_path="Rehab.rdf",
    )
    urls_to_scrape = [
        "https://www.rehabhero.ca/back",
    ]

    # "https://www.rehabhero.ca/neck", https://www.rehabhero.ca/low-back,  https://www.rehabhero.ca/shoulder, https://www.rehabhero.ca/hip,
    # https://www.rehabhero.ca/elbow, https://www.rehabhero.ca/knee, https://www.rehabhero.ca/wrist, https://www.rehabhero.ca/ankle
    # https://www.rehabhero.ca/hand, https://www.rehabhero.ca/foot, https://www.rehabhero.ca/tmj
    category_urls = [
        "https://www.rehabhero.ca/exercise/category/Thoracic+Flexibility",
        "https://www.rehabhero.ca/exercise/category/Thoracic+Strengthening",
        "https://www.rehabhero.ca/exercise/category/Thoracic+Mobility",
        "https://www.rehabhero.ca/exercise/category/Thoracic+Massage",
        "https://www.rehabhero.ca/exercise/category/Thoracic+Stability",
    ]

    crawler.run(urls_to_scrape, category_urls, destination="Scraped_Rehab_Final.rdf")

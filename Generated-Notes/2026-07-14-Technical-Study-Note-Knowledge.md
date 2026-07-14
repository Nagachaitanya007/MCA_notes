---
title: Technical Study Note: Knowledge Representation — Ontologies, Logic, and Semantic Nets
date: 2026-07-14T04:32:15.975805
---

# Technical Study Note: Knowledge Representation — Ontologies, Logic, and Semantic Nets

---

## 1. 🧱 The Core Concept

At scale, modern AI systems cannot rely solely on probabilistic models (like LLMs). To build systems that are **deterministic, explainable, and capable of symbolic reasoning**, we must combine statistical representations with **Knowledge Representation (KR)**. 

KR is the formal study of how an agent models the real world so that a machine can reason over it. We represent knowledge using three foundational paradigms:

```
[Logical Formulas] <---> [Semantic Networks] <---> [Ontologies]
(Inference & Rules)       (Graph Structures)       (Shared Schemas & Semantics)
```

### The Knowledge Representation Spectrum

| Paradigm | Core Representation | Expressive Power | Computational Complexity | Primary Use Case | Industry Standard / Tooling |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Semantic Networks** | Directed labeled graphs ($V$: entities, $E$: relations). | Low to Medium | $O(V + E)$ (graph traversal) | Entity linking, basic semantic search. | Neo4j, Labeled Property Graphs (LPG) |
| **RDF / RDFS** | Directed graphs represented as Subject-Predicate-Object triples. | Medium (Classes, subClassOf, domains, ranges) | Polynomial ($O(N^k)$) for entailment | Linked Open Data, metadata management. | Apache Jena, GraphDB, SPARQL |
| **Description Logics (OWL-DL)** | Decidable fragment of First-Order Logic structured as $TBox$ (schemas) and $ABox$ (data). | High (Union, intersection, cardinality constraints, transitivity) | $NEXPTIME$-complete (decidable) | Automated taxonomy classification, consistency checking. | Protégé, HermiT, Pellet, Stardog |
| **First-Order Logic (FOL)** | Quantifiers ($\forall, \exists$), predicates, and functions. | Very High | Undecidable (semi-decidable) | Mathematical theorem proving, complex planning. | Prolog, z3 Theorem Prover |

### The TBox / ABox Dichotomy (Description Logic)
Knowledge Bases (KBs) built on Description Logics (DL) split information into two distinct stores:
*   **TBox (Terminological Box):** The schema or conceptual model. It defines classes, properties, and constraints (e.g., `ElectricVehicle ⊑ Vehicle`, `hasBattery ⊓ hasMotor`).
*   **ABox (Assertional Box):** The instance data. It asserts facts about specific individuals (e.g., `car_123 Type ElectricVehicle`, `car_123 hasBattery battery_99`).

### Open-World Assumption (OWA) vs. Closed-World Assumption (CWA)
Understanding this distinction is critical when transitioning from relational databases to ontologies:
*   **CWA (Relational Databases / Imperative Code):** If a statement is not explicitly present in the database, it is assumed to be **false**.
*   **OWA (Ontologies / Semantic Web):** If a statement is not present, it is considered **unknown**. The absence of evidence is not evidence of absence. This allows systems to reason over incomplete data without making false assertions.

---

## 2. ⚙️ Under the Hood: Internal Mechanics & Architecture

### Industrial Knowledge Graph Architecture
A production-grade, hybrid Semantic-Probabilistic Search & Reasoning architecture combines LLMs (for extraction and unstructured search) with a deterministic Knowledge Graph (for validation and reasoning).

```
                    +------------------------------------+
                    |  Unstructured Data / Data Lake     |
                    +-------------------+----------------+
                                        |
                                        v
                    +-------------------+----------------+
                    | LLM-based Entity & Relation Extr.  |
                    +-------------------+----------------+
                                        |  (triples)
                                        v
                    +-------------------+----------------+
                    |      Graph Validation Pipeline     | <--- SHACL / ShEx (CWA Constraints)
                    +-------------------+----------------+
                                        |
                                        v
+---------------------------------------+---------------------------------------+
|                               Knowledge Engine                                |
|                                                                               |
|  +--------------------+      +--------------------+      +-----------------+  |
|  |       TBox         |      |       ABox         |      | Rule Engine     |  |
|  |  (Ontology Schema) |      | (Instance Triples) |      | (Rete/Tableau)  |  |
|  +--------------------+      +--------------------+      +-----------------+  |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
                    +-------------------+----------------+
                    |       Semantic Reasoning Engine    |
                    |    (Forward/Backward Chaining)     |
                    +-------------------+----------------+
                                        |
                                        v
                    +-------------------+----------------+
                    |      Query Interface (SPARQL)      |
                    +------------------------------------+
```

### Execution Engine: The Tableau Algorithm
To perform reasoning in OWL-DL (e.g., checking if a TBox is consistent or if $A \sqsubseteq B$), modern reasoners use the **Tableau Algorithm**. 

Instead of searching for proofs directly, a Tableau reasoner checks for consistency by trying to construct a pseudo-model (a tree representation) that satisfies all assertions. If it encounters a **clash** (a direct contradiction like $x \in C$ and $x \in \neg C$) on every branch, the negation of the query is proven, meaning the entailment holds.

#### Conceptual Step-by-Step of the Negation Normal Form (NNF) Expansion:
1. Transform the logical formula so that negations apply only to concept names.
2. Apply expansion rules:
   *   **$\sqcap$-rule (Intersection):** If $x \in (C \sqcap D)$, add $x \in C$ and $x \in D$ to the node.
   *   **$\sqcup$-rule (Union):** If $x \in (C \sqcup D)$, branch the tree: one branch gets $x \in C$, the other gets $x \in D$. This introduces non-determinism.
   *   **$\exists$-rule (Existential):** If $x \in \exists R.C$, create a new successor node $y$ such that $(x, y) \in R$ and $y \in C$.
   *   **$\forall$-rule (Universal):** If $x \in \forall R.C$ and there exists a successor $y$ such that $(x, y) \in R$, add $y \in C$.

### Production Rule Engine: The Rete Algorithm
For forward-chaining rule execution (e.g., in engines like Drools or Jess), evaluating thousands of rules over millions of facts naively results in $O(R \times F^P)$ complexity (where $R$ is rules, $F$ is facts, and $P$ is patterns). The **Rete algorithm** optimizes this to be independent of the number of rules by constructing a directed acyclic graph of conditions.

#### Rete Network Topology:
*   **Alpha Nodes (1-input):** Evaluate single-fact constraints (e.g., `type == "ElectricVehicle"`). They act as filters on the input token stream.
*   **Beta Nodes (2-input):** Evaluate multi-fact joins (e.g., `Vehicle.ownerId == Person.id`). They maintain memories (Alpha memory and Beta memory) of partial matches.
*   **Production Nodes (Terminal):** Represent the RHS (Right-Hand Side) action of a rule that fires when all conditions are satisfied.

```
                  [ Fact Asserted ]
                          |
                          v
                   [ Alpha Node ] (Type == "Vehicle")
                          |
                     (pass token)
                          |
                   [ Beta Node ] (ownerId == Person.id) <--- [ Alpha Node ] (Type == "Person")
                          |
                     (join match)
                          |
                  [ Terminal Node ] ---> (Action: Trigger Tax Credit)
```

---

### Python Implementation: Forward-Chaining Inference Engine
Below is a highly performant, production-mimicking Python implementation of an RDFS-style forward-chaining inference engine. It demonstrates subclass and subproperty propagation with cycle-detection.

```python
from typing import Set, Tuple, Dict, List

# Define types
Triple = Tuple[str, str, str]

class InferenceEngine:
    def __init__(self):
        # ABox: stores explicit and inferred triples
        self.kb: Set[Triple] = set()
        # Indexes for fast lookup O(1)
        self.spo_index: Dict[str, Set[Triple]] = {}
        self.pos_index: Dict[str, Set[Triple]] = {}
        
    def add_triple(self, s: str, p: str, o: str) -> bool:
        triple = (s, p, o)
        if triple in self.kb:
            return False
        
        self.kb.add(triple)
        # Maintain indexes
        self.spo_index.setdefault(s, set()).add(triple)
        self.pos_index.setdefault(p, set()).add(triple)
        return True

    def query(self, s: str = None, p: str = None, o: str = None) -> Set[Triple]:
        """Evaluates basic graph patterns efficiently using indexes."""
        if p and p in self.pos_index:
            candidates = self.pos_index[p]
        elif s and s in self.spo_index:
            candidates = self.spo_index[s]
        else:
            candidates = self.kb

        results = set()
        for triple in candidates:
            ts, tp, to = triple
            if s and s != ts: continue
            if p and p != tp: continue
            if o and o != to: continue
            results.add(triple)
        return results

    def run_rdfs_inference(self) -> int:
        """
        Executes forward-chaining materialization of RDFS-like rules:
        Rule 1 (subClassOf):     (?s rdf:type ?c1) ^ (?c1 rdfs:subClassOf ?c2) -> (?s rdf:type ?c2)
        Rule 2 (subPropertyOf):  (?s ?p1 ?o) ^ (?p1 rdfs:subPropertyOf ?p2) -> (?s ?p2 ?o)
        Rule 3 (domain):         (?s ?p ?o) ^ (?p rdfs:domain ?c) -> (?s rdf:type ?c)
        Rule 4 (range):          (?s ?p ?o) ^ (?p rdfs:range ?c) -> (?o rdf:type ?c)
        """
        inferred_count = 0
        while True:
            new_triples: Set[Triple] = set()

            # Rule 1: Subclass inheritance
            subclass_relations = self.query(p="rdfs:subClassOf")
            for _, c1, c2 in subclass_relations:
                instances = self.query(p="rdf:type", o=c1)
                for s, _, _ in instances:
                    new_triples.add((s, "rdf:type", c2))

            # Rule 2: Subproperty inheritance
            subproperty_relations = self.query(p="rdfs:subPropertyOf")
            for _, p1, p2 in subproperty_relations:
                assertions = self.query(p=p1)
                for s, _, o in assertions:
                    new_triples.add((s, p2, o))

            # Rule 3: Property Domain
            domain_relations = self.query(p="rdfs:domain")
            for p, _, c in domain_relations:
                assertions = self.query(p=p)
                for s, _, _ in assertions:
                    new_triples.add((s, "rdf:type", c))

            # Rule 4: Property Range
            range_relations = self.query(p="rdfs:range")
            for p, _, c in range_relations:
                assertions = self.query(p=p)
                for _, _, o in assertions:
                    new_triples.add((o, "rdf:type", c))

            # Fixpoint iteration check
            added = False
            for t in new_triples:
                if self.add_triple(*t):
                    inferred_count += 1
                    added = True
            
            if not added:
                break # Reached fixed point (no new facts can be inferred)

        return inferred_count

# --- Verification & Demo ---
if __name__ == "__main__":
    engine = InferenceEngine()
    
    # Define TBox
    engine.add_triple("ElectricVehicle", "rdfs:subClassOf", "Vehicle")
    engine.add_triple("hasBatteryPack", "rdfs:subPropertyOf", "hasEnergySource")
    engine.add_triple("hasBatteryPack", "rdfs:domain", "ElectricVehicle")
    engine.add_triple("Battery", "rdfs:subClassOf", "EnergyStorage")
    engine.add_triple("hasBatteryPack", "rdfs:range", "Battery")
    
    # Define ABox
    engine.add_triple("tesla_modelS", "rdf:type", "ElectricVehicle")
    engine.add_triple("tesla_modelS", "hasBatteryPack", "panasonic_cell_pack")
    
    print(f"Explicit Triples in KB: {len(engine.kb)}")
    inferred = engine.run_rdfs_inference()
    print(f"Total Triples Materialized: {inferred}")
    print(f"Total Triples in KB now: {len(engine.kb)}")
    
    # Query inferred facts
    print("\n--- Entailment Assertions ---")
    # Did tesla_modelS get inferred as a Vehicle? (Rule 1)
    print("Is Tesla a Vehicle?", bool(engine.query("tesla_modelS", "rdf:type", "Vehicle")))
    # Did tesla_modelS get hasEnergySource relation? (Rule 2)
    print("Has Tesla Energy Source?", bool(engine.query("tesla_modelS", "hasEnergySource", "panasonic_cell_pack")))
    # Did panasonic_cell_pack infer as Battery (Rule 4) and subsequently EnergyStorage (Rule 1)?
    print("Is cell pack a Battery?", bool(engine.query("panasonic_cell_pack", "rdf:type", "Battery")))
    print("Is cell pack an EnergyStorage?", bool(engine.query("panasonic_cell_pack", "rdf:type", "EnergyStorage")))
```

---

## 3. ⚠️ The Interview Warzone

### System Design Scenario: Deterministic Compatibility Engine (E-Commerce)

#### The Prompt
> **Interviewer:** "We want to design a system that dynamically validates compatibility between physical products (e.g., phone cases and phones, charger blocks and devices) across our 1B+ product catalog. The catalog data is messy, self-reported by 3P merchants, and highly unreliable. 
>
> If we show a bad compatibility match, we lose customer trust. If we miss a match, we lose GMV. The system must be deterministic, highly performant (read queries under $10\text{ms}$), and able to ingest and validate new items dynamically."

---

### The Interviewer's Probing Pattern

An elite interviewer will systematically probe the limits of your proposed architecture, looking for engineering trade-offs:

1.  **The Extraction vs. Validation Trap:**
    *   *Interviewer:* "Why don't we just use a fine-tuned LLM or a vector search engine to find matches?"
    *   *Deep Staff Engineer Answer:* "Because vector search and LLMs are inherently probabilistic. They fail at edge cases like version bounds (e.g., 'iPhone 15 Pro' vs 'iPhone 15'). They cannot guarantee determinism, they hallucinate relations, and they are computationally expensive to run at scale ($10\text{ms}$ SLAs). Instead, we use an LLM *only* to extract candidate assertions into structured triples, but we use a Description Logic (OWL-DL) validator to enforce strict constraints before publishing."

2.  **The Open-World Assumption Dilemma:**
    *   *Interviewer:* "If our ontology says `Device(d) ⊓ (∃hasConnector.USB_C) ⊑ Compatible(d, MacCharger)`, and we insert an unknown device that doesn't state its connector, what happens?"
    *   *Deep Staff Engineer Answer:* "Under the Open-World Assumption, the system will not assume it *is* compatible, nor will it assume it *is not*. It will evaluate as 'unknown'. This prevents false negatives but can block sales. To enforce constraints deterministically on messy web data, we must layer **SHACL (Shapes Constraint Language)** over our ABox. SHACL acts as a Closed-World validation layer on top of our OWA RDF graph, failing validation if required properties (like `hasConnector`) are missing."

3.  **The Reasoning Bottleneck (Scale & Latency):**
    *   *Interviewer:* "Reasoning algorithms like Tableau or Rete are computationally heavy ($NEXPTIME$ or high-degree polynomial). How do you scale this to 1B+ products and serve read requests under $10\text{ms}$?"
    *   *Deep Staff Engineer Answer:* "We must **decouple the write path (Ingestion) from the read path (Querying)** using **Reasoning Materialization**."

```
=== WRITE PATH (Asynchronous, Heavy Compute) ===
Raw Catalog Data ---> LLM Extractor ---> RDF Triples (Raw) ---> Reasoner Engine
                                                                      |
                                                               (Materialize)
                                                                      v
                                                              Fully Closed Triples
                                                                      |
                                                             (Write to Read-Store)
                                                                      v
                                                           [ Read-Optimized NoSQL ]

=== READ PATH (Synchronous, Low Latency) ===
User Query ----------------------------------------------> [ Read-Optimized NoSQL ] (O(1) lookup)
```

By computing all transitive closure rules (e.g., subClassOf, subPropertyOf) at ingestion time, we write the inferred properties directly to the database. The read path becomes a simple $O(1)$ key-value lookup or basic graph traversal without any runtime reasoning.

---

### The Perfect Architecture & Response

To ace this interview, structure your system around a clean segregation of concerns, addressing the schema, validation, ingestion pipeline, and query path.

#### 1. Schema Definition (TBox Ontology)
We write the ontology schema in **W3C Turtle (RDF-S / OWL-DL)** syntax. This defines the core entities, transitive subproperties, and domain constraints:

```turtle
@prefix ex: <http://example.org/compat/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

# Classes
ex:Product rdf:type owl:Class .
ex:Accessory rdf:type owl:Class ; rdfs:subClassOf ex:Product .
ex:HostDevice rdf:type owl:Class ; rdfs:subClassOf ex:Product .

# Properties
ex:hasFormFactor rdf:type owl:ObjectProperty ;
    rdfs:domain ex:Product ;
    rdfs:range ex:FormFactor .

ex:fitsFormFactor rdf:type owl:ObjectProperty ;
    rdfs:domain ex:Accessory ;
    rdfs:range ex:FormFactor .

# Transitive Property for Compatibility propagation
ex:isCompatibleWith rdf:type owl:TransitiveProperty ;
    rdfs:domain ex:Product ;
    rdfs:range ex:Product .
```

#### 2. Closed-World Validation (SHACL)
We define a SHACL shape to guarantee that any incoming product added to the graph contains the required fields needed for reasoning:

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/compat/> .

ex:AccessoryShape a sh:NodeShape ;
    sh:targetClass ex:Accessory ;
    sh:property [
        sh:path ex:fitsFormFactor ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:severity sh:Violation ;
        sh:message "An accessory must fit exactly one specific FormFactor for deterministic matching." ;
    ] .
```

#### 3. Scaling the Ingestion Pipeline (The Write Path)
The ingestion pipeline handles the heavy, non-deterministic, and compute-intensive operations asynchronously:

```
[Merchant Feed] -> [Kafka Topic] -> [LLM Entity Linker (JSON)]
                                            |
                                            v
                                [Data Validator (SHACL)]
                                            |
                                     +------+------+
                                     |             |
                                  (Pass)        (Fail) -> [Dead Letter Queue]
                                     |
                                     v
                        [Graph Reasoner (Incremental)]
                                     |
                            (Materialize Triples)
                                     |
                                     v
                  [Read-Optimized Document Store (DynamoDB)]
```

*   **Ingestion (Kafka):** Incoming catalog changes trigger events.
*   **Entity Extraction:** An LLM parses text descriptions to yield structural RDF assertions (e.g., `ex:Case_A ex:fitsFormFactor ex:FF_iPhone15`).
*   **SHACL Validation:** The assertions are validated against our shapes using a local SHACL processor. Failed items are routed to a human-in-the-loop validation queue.
*   **Incremental Reasoning:** Instead of running reasoning on the entire graph, we use **incremental reasoning** (e.g., using rule networks that only process mutated subgraphs).
*   **Database Write:** The raw and inferred facts (e.g., `ex:Case_A ex:isCompatibleWith ex:Phone_B`) are written to a document store or highly indexed relational DB (e.g., PostgreSQL with index on `(subject, predicate, object)`).

#### 4. Fast Query Serving (The Read Path)
Because the write-path reasoner already materialized all compatibility links, the read-path logic is trivial:

```sql
-- O(1) B-Tree Index lookup to get compatible accessories for a phone
SELECT accessory_id 
FROM product_compatibility 
WHERE host_device_id = 'phone_15_pro' 
  AND compatibility_status = 'VERIFIED';
```

If we need multi-hop graph queries (e.g., finding substitute cases via transitive links), we can use a distributed graph database like Amazon Neptune, queryable in under $10\text{ms}$ because the path length is restricted to pre-computed connections.
# Save as heritage_oodb_sim.py and run: python heritage_oodb_sim.py
import shelve
import uuid
import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional

# -----------------------
# Domain classes (simple)
# -----------------------
def new_id(prefix='id'):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

@dataclass
class Person:
    person_id: str
    name: str
    role: Optional[str] = None

@dataclass
class Institution:
    inst_id: str
    name: str
    address: Optional[str] = None

@dataclass
class ArtifactVersion:
    version_id: str
    timestamp: str
    notes: str
    snapshot: Dict

@dataclass
class DigitalSurrogate:
    surrogate_id: str
    file_ref: str
    file_type: str
    derived_from_id: Optional[str] = None

    def preview_info(self):
        return f"Preview({self.surrogate_id}) -> {self.file_ref} ({self.file_type})"

@dataclass
class ConservationRecord:
    record_id: str
    date: str
    restorer_id: str
    treatment: str
    before_surrogates: List[str] = field(default_factory=list)
    after_surrogates: List[str] = field(default_factory=list)

@dataclass
class Loan:
    loan_id: str
    artifact_id: str
    from_inst: str
    to_inst: str
    start_date: str
    end_date: str
    status: str  # PENDING, ACTIVE, COMPLETED

@dataclass
class Artifact:
    artifact_id: str
    title: str
    creator: str
    date_created: str
    material: Optional[str] = None
    dimensions: Optional[Dict] = None
    provenance: List[Dict] = field(default_factory=list)
    versions: List[ArtifactVersion] = field(default_factory=list)
    digital_surrogates: List[str] = field(default_factory=list)
    conservation_records: List[str] = field(default_factory=list)
    loans: List[str] = field(default_factory=list)

    def current_version(self):
        if not self.versions:
            return None
        return sorted(self.versions, key=lambda v: v.timestamp)[-1]

    def is_on_loan(self, store):
        for loan_id in self.loans:
            loan = store.get('loans', {}).get(loan_id)
            if loan and loan.status == 'ACTIVE':
                return True, loan
        return False, None

    def display_status(self, store):
        onloan, loan = self.is_on_loan(store)
        cv = self.current_version()
        last_conservation = None
        if self.conservation_records:
            crs = [store.get('conservations', {}).get(cid) for cid in self.conservation_records]
            crs = [c for c in crs if c]
            if crs:
                last_conservation = sorted(crs, key=lambda c: c.date)[-1]
        return {
            'artifact_id': self.artifact_id,
            'title': self.title,
            'on_loan': onloan,
            'loan_ref': loan.loan_id if loan else None,
            'current_version': cv.version_id if cv else None,
            'last_conservation': last_conservation.record_id if last_conservation else None
        }

# -----------------------
# Simple OODB-like store
# -----------------------
class SimpleOODB:
    def __init__(self, filename='heritage_store.db'):
        self.dbfile = filename
        self._open_db()

    def _open_db(self):
        self._shelf = shelve.open(self.dbfile, writeback=True)
        for col in ['artifacts', 'digital', 'people', 'institutions', 'loans', 'conservations', 'indexes']:
            if col not in self._shelf:
                self._shelf[col] = {}
        if 'by_title' not in self._shelf['indexes']:
            self._shelf['indexes']['by_title'] = {}

    def save(self):
        self._shelf.sync()

    def close(self):
        self._shelf.close()

    def get(self, collection, key=None):
        col = self._shelf.get(collection, {})
        if key is None:
            return col
        return col.get(key)

    def put(self, collection, key, obj):
        self._shelf[collection][key] = obj
        if collection == 'artifacts':
            idx = self._shelf['indexes'].setdefault('by_title', {})
            idx[obj.title.lower()] = key
        self.save()

    def query_artifacts_by_material(self, material):
        return [a for a in self._shelf['artifacts'].values() if a.material and material.lower() in a.material.lower()]

    def query_conservation_by_restorer(self, restorer_id):
        return [c for c in self._shelf['conservations'].values() if c.restorer_id == restorer_id]

# -----------------------
# Demo operations
# -----------------------
def demo():
    store = SimpleOODB()
    try:
        p1 = Person(person_id=new_id('person'), name='Arun Kumar', role='Restorer')
        inst1 = Institution(inst_id=new_id('inst'), name='Metro Museum')
        inst2 = Institution(inst_id=new_id('inst'), name='City Archive')
        store.put('people', p1.person_id, p1)
        store.put('institutions', inst1.inst_id, inst1)
        store.put('institutions', inst2.inst_id, inst2)
        art = Artifact(artifact_id=new_id('art'), title='Portrait of Marina', creator='Unknown Artist', date_created='1784-01-01', material='oil on canvas', dimensions={'h_cm': 120, 'w_cm': 90})
        v1 = ArtifactVersion(version_id=new_id('ver'), timestamp=str(datetime.datetime.now()), notes='Initial catalog entry', snapshot={'condition': 'fair'})
        art.versions.append(v1)
        d1 = DigitalSurrogate(surrogate_id=new_id('dig'), file_ref='marina_highres.tif', file_type='tif', derived_from_id=art.artifact_id)
        store.put('digital', d1.surrogate_id, d1)
        art.digital_surrogates.append(d1.surrogate_id)
        cons = ConservationRecord(record_id=new_id('cons'), date='2023-08-15', restorer_id=p1.person_id, treatment='cleaning and varnish removal', before_surrogates=[d1.surrogate_id], after_surrogates=[])
        store.put('conservations', cons.record_id, cons)
        art.conservation_records.append(cons.record_id)
        loan = Loan(loan_id=new_id('loan'), artifact_id=art.artifact_id, from_inst=inst1.inst_id, to_inst=inst2.inst_id, start_date='2024-01-10', end_date='2024-04-10', status='ACTIVE')
        store.put('loans', loan.loan_id, loan)
        art.loans.append(loan.loan_id)
        store.put('artifacts', art.artifact_id, art)
        print("\n--- Artifact display status ---")
        a = store.get('artifacts', art.artifact_id)
        print(a.display_status(store._shelf))
        print("\n--- Query artifacts by material 'oil' ---")
        for o in store.query_artifacts_by_material('oil'):
            print(o.artifact_id, o.title, o.material)
        print("\n--- Query conservations by restorer ---")
        for c in store.query_conservation_by_restorer(p1.person_id):
            print(c.record_id, c.date, c.treatment)
        print("\n--- Preview digital surrogate ---")
        d = store.get('digital', d1.surrogate_id)
        print(d.preview_info())
    finally:
        store.close()

if __name__ == '__main__':
    demo()

# dgMP-DosageTextgenerierung-Skript

[![CI](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/actions/workflows/ci.yml/badge.svg)](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/actions/workflows/ci.yml)
[![Release](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/actions/workflows/release.yml/badge.svg)](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/actions/workflows/release.yml)
[![Release On Tag](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/actions/workflows/release-on-tag.yml/badge.svg)](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/actions/workflows/release-on-tag.yml)
[![FHIR R4](https://img.shields.io/badge/FHIR-R4-0A4A8B)](https://hl7.org/fhir/R4/)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Spezifikation und Python-Referenzimplementierung des Algorithmus zur Dosierungstext-Generierung im Rahmen des [Medication IG DE](https://ig.fhir.de/igs/medication/).

## Inhalt

| Datei | Beschreibung |
|-------|--------------|
| [dosage-text-algorithm-spec.md](dosage-text-algorithm-spec.md) | **Normative Spezifikation** des Algorithmus — verbindlich für alle Implementierungen |
| [medication-dosage-to-text.py](medication-dosage-to-text.py) | Python-Referenzimplementierung — dient der Veranschaulichung, nicht als Standard |

**Die Spezifikation ist führend.** Weicht das Skript von ihr ab, gilt die Spezifikation. Die in `__version__` geführte Versionsnummer des Skripts bezeichnet die umgesetzte Algorithmus-Version und entspricht der in der Spezifikation angegebenen.

## HAFTUNGSAUSSCHLUSS

Diese Referenzimplementierung wird ausschließlich zu Demonstrations- und Evaluierungszwecken bereitgestellt.  
Sie ist nicht für den produktiven Einsatz vorgesehen und kann unvollständig, fehlerhaft oder nicht konform zu geltenden Standards sein.  

Die Implementierung wird „wie besehen“ (AS IS) bereitgestellt, ohne jegliche ausdrückliche oder stillschweigende Gewährleistung, einschließlich, aber nicht beschränkt auf die Gewährleistung der Marktgängigkeit, Eignung für einen bestimmten Zweck oder Nichtverletzung von Rechten Dritter.  

In keinem Fall haften die Autor:innen, Mitwirkenden oder bereitstellenden Organisationen für Ansprüche, Schäden oder sonstige Haftung – gleich aus welchem Rechtsgrund –, die sich aus der Nutzung der Referenzimplementierung oder deren Einsatz ergeben.  

Die Nutzer:innen dieser Referenzimplementierung tragen die alleinige Verantwortung dafür, deren Eignung, Korrektheit und Konformität mit relevanten rechtlichen, regulatorischen und sicherheitsrelevanten Anforderungen vor jeglicher Nutzung über Demonstrations- oder Testzwecke hinaus zu prüfen.

## Weitere Informationen

Änderungshistorie: siehe [CHANGELOG.md](CHANGELOG.md).

Alle veröffentlichten Versionen: [GitHub Releases](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/releases)

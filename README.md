# Novelty Score
# Description

This code computes the novelty score for the results obtained for a 1 hop response. This is computed inside the [SRI answer appraiser](https://github.com/NCATSTranslator/Translator-All/wiki/Standards-and-Reference-Implementation-(SRI)-Team).

The Novelty Score calculation would be skipped for a drug entity with available [Clinical Evidence](https://github.com/NCATSTranslator/Translator-All/wiki/SRI-Clinical-Evidence-Score).  
At the first step, the results are distinguished into so called ''known’’ whose resource_id is among inferring sources of 'infores:aragorn', 'infores:arax', 'infores:biothings-explorer', 'infores:improving-agent', 'infores:robokop' otherwise is called  ``unknown’’.  

The Novelty Score considers three factors, namely, **Recency**, **Molecular structure Similarity** and **FDA Approval**.

1. **Recency**:
  - The list PMID/PMC-ID of publications associated to each drug are collected from the EPC attributes where attribute_type_id is among 'biolink:publications' or 'biolink:Publication' or 'biolink:publication'.
  - The PMID/PMC-ID are sent to the API of [Text Mining Provider](https://github.com/NCATSTranslator/Translator-All/wiki/Text-Mining-Provider) KP returning the publishing date for each publication    
  
The number of publications and age of oldest publication are combined into a Sigmoid function to produce a value for recency for the result. The recency is a floating number between 0 and 1; a very recent drug would have the recency of 1. The computed recency value is used as a base value to be modified by other factors to reach the final Novelty Score.	


2. **Molecular Structure Similarity**:

When the result is a drug, the molecular similarity is computed by comparing the drug in the result against all drugs indicated in lookup (known) results produced for the same query. a pervasive concept in chemistry, it is essential to many aspects of chemical reasoning and analysis. It computes a drug entity’s pairwise structure similarity to prior drug entities. This is computed as follows:
  - The drug entity’s ID is sent to the API of [Molecular Data Provider](https://github.com/NCATSTranslator/Translator-All/wiki/Molecular-Data-Provider) KP to extract the Simplified Molecular-Input Line-Entry system (SMILE).
  - [Open-source Cheminformatics software (RDKit)](https://www.rdkit.org/) is used to calculate the pairwise similarity between two drug entities by calculating the Jaccard coefficient. Finally, the global similarity in our study would be the highest similarity score between the target drug entity against the other existing ``known’’ drugs. The similarity score is a floating number between 0 and 1 where 1 represents the score between two completely similar molecules. Indicate how it modified the base recency number.

3. **FDA Approval Status**:
  - When the result is a drug, we consider if it is either FDA approved or not (including different FDA drug stages) assigned to be 0 and 1, respectively. The novelty score of a drug entity with FDA approval, reduced by 0.85 coefficient.

The calculation of the Novelty Score for each drug entity begins with evaluating recency, which takes into account the number of associated publications and the age of the oldest publication. Subsequently, the impact of molecular similarity and FDA approval status is applied to modify the initial Novelty Score. Specifically, if the molecular similarity is below 0.5, indicating a relatively unique molecule, the Novelty Score receives a boost via a coefficient. However, if the drug entity possesses FDA approval, the Novelty Score is reduced by a coefficient of 0.85.
In cases where recency calculation is not feasible for a particular drug entity, the base of the Novelty Score is established using molecular similarity.
...

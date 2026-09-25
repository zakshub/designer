# Designer–Studio contract

Designer owns intent, audience, hierarchy, composition, accessibility, placement and acceptance criteria. Studio owns image-production reasoning, assets, rights/provenance and image QC.

Brief fields: id, owner=designer, intent, audience, placement, composition, accessibility, acceptance_criteria. Delivery fields: brief_id, owner=studio, asset_uri, production_rationale, rights, image_qc, design_fit_qc.

Each QC contains owner, reviewer, status (pending/pass/fail) and findings. Studio owns image_qc; Designer owns design_fit_qc. Both must pass for acceptance.

sentinel.studio.evaluate_delivery validates the contract. It does not inspect pixels, generate imagery or verify rights externally. Findings must come from the responsible reviewers.

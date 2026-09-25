import copy
import unittest

from sentinel.model import Invalid
from sentinel.studio import evaluate_delivery


class StudioContractTests(unittest.TestCase):
    def setUp(self):
        self.brief = {"id": "brief-1", "owner": "designer", "intent": "Explain the collection concept", "audience": "Design reviewers",
                      "placement": "Collection overview", "composition": "Room for the title", "accessibility": "Meaningful alt text",
                      "acceptance_criteria": ["Fits the concept", "Title remains readable"]}
        self.delivery = {"brief_id": "brief-1", "owner": "studio", "asset_uri": "https://example.invalid/asset.png",
                         "production_rationale": "Synthetic test delivery", "rights": "Synthetic asset reference only",
                         "image_qc": {"owner": "studio", "reviewer": "simulated-studio", "status": "pass", "findings": "Synthetic image-QC pass"},
                         "design_fit_qc": {"owner": "designer", "reviewer": "simulated-designer", "status": "pending", "findings": "Fit not inspected"}}

    def test_image_pass_does_not_imply_design_acceptance(self):
        self.assertFalse(evaluate_delivery(self.brief, self.delivery)["accepted"])

    def test_both_reviews_required(self):
        self.delivery["design_fit_qc"]["status"] = "pass"
        self.assertTrue(evaluate_delivery(self.brief, self.delivery)["accepted"])
        self.delivery["image_qc"]["status"] = "fail"
        self.assertFalse(evaluate_delivery(self.brief, self.delivery)["accepted"])

    def test_role_confusion_rejected(self):
        self.delivery["design_fit_qc"]["owner"] = "studio"
        with self.assertRaises(Invalid):
            evaluate_delivery(self.brief, self.delivery)

    def test_wrong_brief_rejected(self):
        self.delivery["brief_id"] = "another-brief"
        with self.assertRaises(Invalid):
            evaluate_delivery(self.brief, self.delivery)

    def test_missing_fields_rejected(self):
        for field in self.brief:
            obj = copy.deepcopy(self.brief)
            del obj[field]
            with self.assertRaises(Invalid):
                evaluate_delivery(obj, self.delivery)

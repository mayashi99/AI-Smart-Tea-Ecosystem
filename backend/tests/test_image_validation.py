from io import BytesIO
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from PIL import Image
from app.components.Component02.image_validation import validate_tea_image, MAX_IMAGE_BYTES


class ImageValidationTests(unittest.TestCase):
    def image_bytes(self):
        output = BytesIO()
        Image.new('RGB', (64, 64), 'white').save(output, format='PNG')
        return output.getvalue()

    def test_corrupt_upload_rejected_before_model(self):
        with patch('app.components.Component02.image_validation._is_tea_image') as model:
            with self.assertRaises(HTTPException) as error:
                validate_tea_image(b'not an image', 'fake.png')
            self.assertEqual(error.exception.status_code, 400)
            model.assert_not_called()

    def test_unrelated_image_rejected_with_filename(self):
        with patch('app.components.Component02.image_validation._is_tea_image', return_value=False):
            with self.assertRaises(HTTPException) as error:
                validate_tea_image(self.image_bytes(), 'car.png')
            self.assertEqual(error.exception.status_code, 422)
            self.assertIn('car.png', error.exception.detail)
            self.assertIn('tea leaves', error.exception.detail)

    def test_accepted_image_passes(self):
        with patch('app.components.Component02.image_validation._is_tea_image', return_value=True):
            validate_tea_image(self.image_bytes(), 'tea.png')

    def test_model_failure_does_not_allow_analysis(self):
        with patch('app.components.Component02.image_validation._is_tea_image', side_effect=RuntimeError):
            with self.assertRaises(HTTPException) as error:
                validate_tea_image(self.image_bytes(), 'tea.png')
            self.assertEqual(error.exception.status_code, 503)

    def test_oversized_image_rejected(self):
        with self.assertRaises(HTTPException) as error:
            validate_tea_image(b'x' * (MAX_IMAGE_BYTES + 1), 'large.png')
        self.assertEqual(error.exception.status_code, 413)


if __name__ == '__main__':
    unittest.main()

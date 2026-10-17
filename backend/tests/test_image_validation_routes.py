from io import BytesIO
import unittest
from unittest.mock import patch
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from app.components.Component02 import api
from app.components.Component02.harvest_readiness import api as readiness_api


class ImageValidationRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_readiness_rejects_non_tea_before_loading_model(self):
        file = UploadFile(BytesIO(b'car'), filename='car.jpg',
                          headers=Headers({'content-type': 'image/jpeg'}))
        with patch.object(readiness_api, 'validate_tea_image', side_effect=HTTPException(422, 'Not tea')), \
                patch.object(readiness_api, 'get_model') as model:
            with self.assertRaises(HTTPException) as error:
                await readiness_api.predict(file)
            self.assertEqual(error.exception.status_code, 422)
            model.assert_not_called()

    async def test_mixed_batch_never_reaches_health_model(self):
        files = [UploadFile(BytesIO(b'tea'), filename='tea.jpg'),
                 UploadFile(BytesIO(b'car'), filename='car.jpg')]
        with patch.object(api, 'validate_tea_image', side_effect=[None, HTTPException(422, 'Not tea')]), \
                patch.object(api.model, 'predict') as predict:
            with self.assertRaises(HTTPException) as error:
                await api.assess_plantation(files=files, file=None)
            self.assertEqual(error.exception.status_code, 422)
            predict.assert_not_called()

    async def test_upload_validation_accepts_valid_batch(self):
        with patch.object(api, 'validate_tea_image') as validate:
            result = await api.validate_images([UploadFile(BytesIO(b'tea'), filename='tea.jpg')])
            self.assertEqual(result, {'success': True})
            validate.assert_called_once_with(b'tea', 'tea.jpg')

    async def test_upload_validation_rejects_empty_batch(self):
        with self.assertRaises(HTTPException) as error:
            await api.validate_images([])
        self.assertEqual(error.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()

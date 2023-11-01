from abc import ABC
from typing import Any, Iterable, Mapping, MutableMapping, Optional

import requests
from airbyte_cdk.sources.streams.http import HttpStream
# from airbyte_cdk.sources.utils.transform import TransformConfig, TypeTransformer


class PendoPythonStream(HttpStream, ABC):
    url_base = "https://app.pendo.io/api/v1/"
    primary_key = "id"

    # transformer = TypeTransformer(TransformConfig.CustomSchemaNormalization)

    # def __init__(self, *args,  **kwargs):
    #     super().__init__(*args, **kwargs)
    #     transform_function = self.get_custom_transform()
    #     self.transformer.registerCustomTransform(transform_function)

    # @staticmethod
    # def get_custom_transform():
    #     def custom_transform_function(original_value, field_schema):
    #         if original_value:
    #             print("original_value: ", original_value)
    #             print("field_schema: ", field_schema)
    #             if not isinstance(original_value, dict):
    #                 print("original value is not a dict")
    #                 if "format" in field_schema and field_schema["format"] == "date-time":
    #                     print("Converting to string: ", original_value)
    #                     return str(original_value)
    #         return original_value

    #     return custom_transform_function

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        return None

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        return {}

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        yield from response.json()

    # Method to get an Airbyte field schema for a given Pendo field type
    def get_valid_field_info(self, field_type) -> dict:
        output = {}
        if field_type == 'time':
            output["type"] = ["null", "integer"]
        elif field_type == 'list':
            output["type"] = ["null", "array"]
        elif field_type == '':
            output['type'] = ["null", "array", "string", "integer", "boolean"]
        else:
            output["type"] = ["null", field_type]
        return output

    # Build the Airbyte stream schema from Pendo metadata
    def build_schema(self, full_schema, metadata):
        for key in metadata:
            if not key.startswith("auto"):
                fields = {}
                for field in metadata[key]:
                    field_type = metadata[key][field]['Type']
                    fields[field] = self.get_valid_field_info(field_type)

                full_schema['properties']['metadata']['properties'][key] = {
                    "type": ["null", "object"],
                    "properties": fields
                }
        return full_schema


# Airbyte Streams using the Pendo /aggregation endpoint (Currently only Account and Visitor)
class PendoAggregationStream(PendoPythonStream):
    json_schema = None  # Field to store dynamically built Airbyte Stream Schema
    page_size = 10

    @property
    def http_method(self) -> str:
        return "POST"

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "aggregation"

    def request_headers(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> Mapping[str, Any]:
        return {"Content-Type": "application/json"}

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        data = response.json().get("results", [])
        if len(data) < self.page_size:
            return None
        return data[-1][self.primary_key]

    def parse_response(
        self, response: requests.Response, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, **kwargss
    ) -> Iterable[Mapping]:
        """
        :return an iterable containing each record in the response
        """
        yield from response.json().get("results", [])

    # Build /aggregation endpoint payload with pagination for a given source and requestId
    def build_request_body(self, requestId, source, next_page_token) -> Optional[Mapping[str, Any]]:
        request_body = {
            "response": {"mimeType": "application/json"},
            "request": {
                "requestId": requestId,
                "pipeline": [
                    {"source": source},
                    {"sort": [self.primary_key]},
                    {"limit": self.page_size},
                ],
            },
        }

        if next_page_token is not None:
            request_body["request"]["pipeline"].insert(
                2, {"filter": f"{self.primary_key} > \"{next_page_token}\""}
            )

        return request_body


class Feature(PendoPythonStream):
    name = "feature"

    def path(self, stream_slice: Mapping[str, Any] = None, **kwargs) -> str:
        return "feature"


class Guide(PendoPythonStream):
    name = "guide"

    def path(self, stream_slice: Mapping[str, Any] = None, **kwargs) -> str:
        return "guide"


class Page(PendoPythonStream):
    name = "page"

    def path(self, stream_slice: Mapping[str, Any] = None, **kwargs) -> str:
        return "page"


class Report(PendoPythonStream):
    name = "report"

    def path(self, stream_slice: Mapping[str, Any] = None, **kwargs) -> str:
        return "report"


class VisitorMetadata(PendoPythonStream):
    name = "visitor metadata"

    def path(self, stream_slice: Mapping[str, Any] = None, **kwargs) -> str:
        return "metadata/schema/visitor"

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        yield from [response.json()]


class AccountMetadata(PendoPythonStream):
    name = "account metadata"

    def path(self, stream_slice: Mapping[str, Any] = None, **kwargs) -> str:
        return "metadata/schema/account"

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        yield from [response.json()]


class Visitors(PendoAggregationStream):
    primary_key = "visitorId"

    name = "visitor"

    def get_json_schema(self) -> Mapping[str, Any]:
        if self.json_schema is None:
            base_schema = super().get_json_schema()
            url = f"{PendoPythonStream.url_base}metadata/schema/visitor"
            auth_headers = self.authenticator.get_auth_header()
            try:
                session = requests.get(url, headers=auth_headers)
                body = session.json()

                full_schema = base_schema
                full_schema['properties']['metadata']['properties']['auto__323232'] = {
                    "type": ["null", "object"]
                }

                auto_fields = {
                    "lastupdated": {
                        "type": ["null", "integer"],
                        # "format": "date-time",
                        # "airbyte_type": "timestamp_without_timezone"
                    },
                    "idhash": {
                        "type": ["null", "integer"]
                    },
                    "lastuseragent": {
                        "type": ["null", "string"]
                    },
                    "lastmetadataupdate_agent": {
                        "type": ["null", "integer"]
                    }
                }
                for key in body['auto']:
                    auto_fields[key] = self.get_valid_field_info(body['auto'][key]['Type'])
                full_schema['properties']['metadata']['properties']['auto']['properties'] = auto_fields
                full_schema['properties']['metadata']['properties']['auto__323232']['properties'] = auto_fields

                full_schema = self.build_schema(full_schema, body)
                self.json_schema = full_schema
            except requests.exceptions.RequestException:
                self.json_schema = base_schema
        return self.json_schema

    def request_body_json(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Optional[Mapping[str, Any]]:
        source = {
            "visitors": {
                "identified": True
            }
        }
        return self.build_request_body("visitor-list", source, next_page_token)


class Accounts(PendoAggregationStream):
    primary_key = "accountId"

    name = "account"

    def get_json_schema(self) -> Mapping[str, Any]:
        if self.json_schema is None:
            base_schema = super().get_json_schema()
            url = f"{PendoPythonStream.url_base}metadata/schema/account"
            auth_headers = self.authenticator.get_auth_header()
            try:
                session = requests.get(url, headers=auth_headers)
                body = session.json()

                full_schema = base_schema
                full_schema['properties']['metadata']['properties']['auto__323232'] = {
                    "type": ["null", "object"]
                }

                auto_fields = {
                    "lastupdated": {
                        "type": ["null", "integer"],
                        # "format": "date-time",
                        # "airbyte_type": "timestamp_without_timezone"
                    },
                    "idhash": {
                        "type": ["null", "integer"]
                    }
                }
                for key in body['auto']:
                    auto_fields[key] = self.get_valid_field_info(body['auto'][key]['Type'])
                full_schema['properties']['metadata']['properties']['auto']['properties'] = auto_fields
                full_schema['properties']['metadata']['properties']['auto__323232']['properties'] = auto_fields

                full_schema = self.build_schema(full_schema, body)
                self.json_schema = full_schema
            except requests.exceptions.RequestException:
                self.json_schema = base_schema
        return self.json_schema

    def request_body_json(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Optional[Mapping[str, Any]]:
        source = {"accounts": {}}
        return self.build_request_body("account-list", source, next_page_token)

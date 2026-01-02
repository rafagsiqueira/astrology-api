
import httpx
import json
from google.genai import errors
from google.genai._api_client import BaseApiClient, HttpResponse

async def _async_request_patched(self, http_request, stream=False):
    if self.vertexai:
      http_request.headers['Authorization'] = (
          f'Bearer {await self._async_access_token()}'
      )
      if self._credentials.quota_project_id:
        http_request.headers['x-goog-user-project'] = (
            self._credentials.quota_project_id
        )
    if stream:
      httpx_request = httpx.Request(
          method=http_request.method,
          url=http_request.url,
          content=json.dumps(http_request.data),
          headers=http_request.headers,
      )
      # FIX: Pass timeout to AsyncClient
      aclient = httpx.AsyncClient(timeout=http_request.timeout)
      response = await aclient.send(
          httpx_request,
          stream=stream,
      )
      try:
          errors.APIError.raise_for_response(response)
      except Exception:
          # best effort to close if we are raising
          await aclient.aclose()
          raise

      # Note: We are not closing aclient here because the stream needs it open.
      # Ideally we should attach aclient close to response close, but we follow original SDK pattern mostly.
      return HttpResponse(
          response.headers, response if stream else [response.text]
      )
    else:
      async with httpx.AsyncClient() as aclient:
        response = await aclient.request(
            method=http_request.method,
            url=http_request.url,
            headers=http_request.headers,
            content=json.dumps(http_request.data) if http_request.data else None,
            timeout=http_request.timeout,
        )
        errors.APIError.raise_for_response(response)
        return HttpResponse(
            response.headers, response if stream else [response.text]
        )

def apply_patch():
    BaseApiClient._async_request = _async_request_patched

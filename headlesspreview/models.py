import datetime
import json
import urllib
import uuid

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.shortcuts import render


class PagePreview(models.Model):
    identifier = models.CharField(db_index=True, max_length=255)
    token = models.CharField(max_length=255)
    content_json = models.TextField()
    created_at = models.DateField(auto_now_add=True)

    @staticmethod
    def from_page(page):
        if page.pk is None:
            identifier = "parent_id=%d;page_type=%s" % (page.get_parent().pk, page._meta.label)
        else:
            identifier = "id=%d" % page.pk

        return PagePreview(
            identifier=identifier,
            content_json=page.to_json()
        )

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def as_page(self):
        content = json.loads(self.content_json)
        page_model = ContentType.objects.get_for_id(content['content_type']).model_class()
        page = page_model.from_json(self.content_json)
        page.pk = content['pk']
        return page

    @staticmethod
    def garbage_collect():
        yesterday = datetime.datetime.now() - datetime.timedelta(hours=24)
        PagePreview.objects.filter(created_at__lt=yesterday).delete()


class HeadlessPreviewMixin():
    def get_client_root_url(self):
        # single client:
        # return settings.HEADLESS_PREVIEW_CLIENT_URL

        # per-site clients
        try:
            return settings.HEADLESS_PREVIEW_CLIENT_URLS[self.get_site().hostname]
        except KeyError:
            return settings.HEADLESS_PREVIEW_CLIENT_URLS['default']

    def serve_preview(self, request, mode_name):
        page_preview = PagePreview.from_page(self)
        page_preview.save()
        PagePreview.garbage_collect()

        client_url = self.get_client_root_url() + '?' + urllib.parse.urlencode({
            'identifier': page_preview.identifier,
            'token': page_preview.token,
        })

        return render(request, 'headless_preview/frame.html', {
            'page': self,
            'client_url': client_url,
        })

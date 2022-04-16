# import pytest


class TestMessage:
    def test___str__(self):  # synced
        assert True

    def test___call__(self):  # synced
        assert True

    def test___hash__(self):  # synced
        assert True

    def test___contains__(self):  # synced
        assert True

    def test_render(self):  # synced
        assert True

    def test_change_category_to(self):  # synced
        assert True

    def test_add_labels(self):  # synced
        assert True

    def test_remove_labels(self):  # synced
        assert True

    def test_mark_is_read(self):  # synced
        assert True

    def test_mark_is_important(self):  # synced
        assert True

    def test_mark_is_starred(self):  # synced
        assert True

    def test_archive(self):  # synced
        assert True

    def test_trash(self):  # synced
        assert True

    def test_untrash(self):  # synced
        assert True

    def test_delete(self):  # synced
        assert True

    def test_reply(self):  # synced
        assert True

    def test_forward(self):  # synced
        assert True

    def test_refresh(self):  # synced
        assert True

    def test__set_attributes_from_resource(self):  # synced
        assert True

    def test_from_id(self):  # synced
        assert True

    class TestAttribute:
        class TestFrom:
            pass

        class TestTo:
            pass

        class TestCc:
            pass

        class TestBcc:
            pass

        class TestSubject:
            pass

        class TestFileName:
            pass

        class TestDate:
            def test__coerce(self):  # synced
                assert True

        class TestSize:
            pass

        class TestHas:
            class TestAttachment:
                pass

            class TestYoutubeVideo:
                pass

            class TestGoogleDrive:
                pass

            class TestGoogleDocs:
                pass

            class TestGoogleSheets:
                pass

            class TestGoogleSlides:
                pass

            class TestUserLabel:
                pass


class TestContact:
    def test___str__(self):  # synced
        assert True

    def test___eq__(self):  # synced
        assert True

    def test_or_none(self):  # synced
        assert True

    def test_many_or_none(self):  # synced
        assert True


class TestBody:
    def test___str__(self):  # synced
        assert True

    def test__repr_html_(self):  # synced
        assert True


class TestAttachments:
    def test_save_to(self):  # synced
        assert True


class TestAttachment:
    def test_save_to(self):  # synced
        assert True

    def test_save_as(self):  # synced
        assert True

    def test__save(self):  # synced
        assert True

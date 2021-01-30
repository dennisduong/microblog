import unittest

from peewee import SqliteDatabase

from microblog import Post, Tag

# use an in-memory SQLite for tests.
db = SqliteDatabase(':memory:', pragmas={'foreign_keys': 1})

PostTag = Tag.posts.get_through_model()


class BaseTestCase(unittest.TestCase):

    models = [Post, Tag, PostTag]

    def setUp(self):
        db.bind(self.models)
        db.create_tables(self.models, safe=True)

    def tearDown(self):
        # Not strictly necessary since SQLite in-memory databases only live
        # for the duration of the connection, and in the next step we close
        # the connection...but a good practice all the same.
        db.drop_tables(self.models)

        # Close connection to db.
        db.close()

        # If we wanted, we could re-bind the models to their original
        # database here. But for tests this is probably not necessary.

    def test_delete_post(self):
        """it can remove post from database along with association table rows."""
        post = Post.create(
            title='My First Blog Post',
            description='Welcome to my blog!',
            content='# Introduction')
        post.tags.add([
            Tag.create(name='programming'), 
            Tag.create(name='personal')
        ])
        self.assertEqual(PostTag.select().count(), 2)
        post.delete_instance()
        self.assertEqual(Post.select().count(), 0)
        self.assertEqual(PostTag.select().count(), 0)

    def test_delete_tag(self):
        """it can remove tag from database along with association table rows."""
        tag = Tag.create(name='programming')
        post = Post.create(
            title='My First Blog Post',
            description='Welcome to my blog!',
            content='# Introduction')
        post.tags.add(tag)
        self.assertEqual(PostTag.select().count(), 1)
        self.assertEqual(Post.select().first().tags.count(), 1)
        tag.delete_instance()
        self.assertEqual(PostTag.select().count(), 0)
        self.assertEqual(Post.select().first().tags.count(), 0)

if __name__ == '__main__':
    unittest.main()
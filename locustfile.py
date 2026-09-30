from locust import HttpUser, task, between


class ExploreUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def view_explore_page(self):
        self.client.get("/api/projects/")

    @task(2)
    def search_projects(self):
        self.client.get("/api/projects/?search=react")

    @task(1)
    def view_project_detail(self):
        self.client.get("/api/projects/my-second-project/")

    @task(1)
    def get_demo_url(self):
        self.client.get("/api/projects/my-second-project/demo-url/")
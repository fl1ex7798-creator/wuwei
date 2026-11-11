package com.example.hello;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class HelloApplicationTests {
    @Autowired MockMvc mvc;

    @Test
    void anonymousCannotAccessHello() throws Exception {
        mvc.perform(get("/api/hello")).andExpect(status().isUnauthorized());
    }

    @Test
    void loginSessionCanAccessHelloAndLogout() throws Exception {
        var result = mvc.perform(post("/api/login").with(csrf())
                        .param("username", "test").param("password", "123456"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("test")).andReturn();
        var session = (MockHttpSession) result.getRequest().getSession(false);
        assertNotNull(session);
        mvc.perform(get("/api/hello").session(session))
                .andExpect(status().isOk()).andExpect(content().string("Hello World"));
        mvc.perform(post("/api/logout").session(session).with(csrf()))
                .andExpect(status().isNoContent());
        mvc.perform(get("/api/hello")).andExpect(status().isUnauthorized());
    }

    @Test
    void invalidPasswordIsRejected() throws Exception {
        mvc.perform(post("/api/login").with(csrf())
                        .param("username", "test").param("password", "wrong"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error").value("Invalid username or password"));
    }

    @Test
    void csrfTokenIsPublicAndLoginRequiresIt() throws Exception {
        mvc.perform(get("/api/csrf")).andExpect(status().isOk())
                .andExpect(jsonPath("$.token").isNotEmpty());
        mvc.perform(post("/api/login").param("username", "test").param("password", "123456"))
                .andExpect(status().isForbidden());
    }
}

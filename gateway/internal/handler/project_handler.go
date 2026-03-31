package handler

import (
	"strconv"

	"github.com/arboris-novel/gateway/internal/auth"
	"github.com/arboris-novel/gateway/internal/service"
	"github.com/arboris-novel/gateway/pkg/response"
	"github.com/gofiber/fiber/v2"
)

type ProjectHandler struct {
	projectSvc *service.ProjectService
}

func NewProjectHandler(projectSvc *service.ProjectService) *ProjectHandler {
	return &ProjectHandler{projectSvc: projectSvc}
}

func (h *ProjectHandler) RegisterRoutes(router fiber.Router) {
	novels := router.Group("/novels", auth.JWTMiddleware())
	novels.Get("/", h.ListProjects)
	novels.Get("/:project_id", h.GetProject)
	novels.Get("/:project_id/sections/:section", h.GetSection)
	novels.Get("/:project_id/chapters/:chapter_number", h.GetChapter)
}

func (h *ProjectHandler) ListProjects(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	page, _ := strconv.Atoi(c.Query("page", "1"))
	pageSize, _ := strconv.Atoi(c.Query("page_size", "20"))

	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	projects, total, err := h.projectSvc.ListProjects(c.Context(), userID, page, pageSize)
	if err != nil {
		return response.InternalError(c, "failed to list projects")
	}

	return response.Paginated(c, projects, total, page, pageSize)
}

func (h *ProjectHandler) GetProject(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	projectID := c.Params("project_id")
	includeContent := c.Query("include_content", "true") == "true"

	project, err := h.projectSvc.GetProject(c.Context(), projectID, userID, includeContent)
	if err != nil {
		if err == service.ErrProjectNotFound {
			return response.NotFound(c, "project not found")
		}
		return response.InternalError(c, "failed to load project")
	}

	return response.OK(c, project)
}

func (h *ProjectHandler) GetSection(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	projectID := c.Params("project_id")
	section := service.SectionName(c.Params("section"))

	data, err := h.projectSvc.GetSection(c.Context(), projectID, userID, section)
	if err != nil {
		if err == service.ErrProjectNotFound {
			return response.NotFound(c, "project not found")
		}
		return response.InternalError(c, err.Error())
	}

	return response.OK(c, data)
}

func (h *ProjectHandler) GetChapter(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	projectID := c.Params("project_id")
	chapterNumber, err := strconv.Atoi(c.Params("chapter_number"))
	if err != nil {
		return response.BadRequest(c, "invalid chapter number")
	}

	chapter, err := h.projectSvc.GetChapter(c.Context(), projectID, userID, chapterNumber)
	if err != nil {
		if err == service.ErrProjectNotFound {
			return response.NotFound(c, "project not found")
		}
		return response.InternalError(c, "failed to load chapter")
	}

	return response.OK(c, chapter)
}

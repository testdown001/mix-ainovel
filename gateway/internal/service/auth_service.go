package service

import (
	"context"
	"errors"
	"time"

	"github.com/arboris-novel/gateway/internal/config"
	"github.com/arboris-novel/gateway/internal/models"
	"github.com/arboris-novel/gateway/internal/repository"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
)

var (
	ErrInvalidCredentials = errors.New("invalid username or password")
	ErrRegistrationClosed = errors.New("registration is currently disabled")
)

type AuthService struct {
	userRepo  *repository.UserRepository
	quotaRepo *repository.QuotaRepository
	cfg       *config.Config
}

func NewAuthService(userRepo *repository.UserRepository, quotaRepo *repository.QuotaRepository, cfg *config.Config) *AuthService {
	return &AuthService{
		userRepo:  userRepo,
		quotaRepo: quotaRepo,
		cfg:       cfg,
	}
}

type TokenResponse struct {
	AccessToken        string `json:"access_token"`
	TokenType          string `json:"token_type"`
	MustChangePassword bool   `json:"must_change_password"`
}

func (s *AuthService) Register(ctx context.Context, username, email, password string) (*models.User, error) {
	hashed, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}

	user := &models.User{
		Username:       username,
		HashedPassword: string(hashed),
		IsAdmin:        false,
		IsActive:       true,
	}
	if email != "" {
		user.Email = &email
	}

	if err := s.userRepo.Create(ctx, user); err != nil {
		return nil, err
	}

	if _, err := s.quotaRepo.GetOrCreate(ctx, user.ID); err != nil {
		return nil, err
	}

	return user, nil
}

func (s *AuthService) Login(ctx context.Context, username, password string) (*TokenResponse, error) {
	user, err := s.userRepo.FindByUsername(ctx, username)
	if err != nil {
		return nil, ErrInvalidCredentials
	}

	if !user.IsActive {
		return nil, ErrInvalidCredentials
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.HashedPassword), []byte(password)); err != nil {
		return nil, ErrInvalidCredentials
	}

	token, err := s.createAccessToken(user)
	if err != nil {
		return nil, err
	}

	mustChange := s.mustChangePassword(user, password)

	return &TokenResponse{
		AccessToken:        token,
		TokenType:          "bearer",
		MustChangePassword: mustChange,
	}, nil
}

func (s *AuthService) createAccessToken(user *models.User) (string, error) {
	now := time.Now().UTC()

	claims := jwt.MapClaims{
		"sub":        user.Username,
		"user_id":    user.ID,
		"username":   user.Username,
		"is_admin":   user.IsAdmin,
		"is_premium": false,
		"iss":        s.cfg.JWT.Issuer,
		"aud":        s.cfg.JWT.Audience,
		"iat":        now.Unix(),
		"exp":        now.Add(24 * time.Hour).Unix(),
	}

	if user.Quota != nil {
		claims["is_premium"] = user.Quota.IsPremium
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(s.cfg.JWT.Secret))
}

func (s *AuthService) mustChangePassword(user *models.User, plainPassword string) bool {
	if !user.IsAdmin {
		return false
	}
	return user.Username == "admin"
}

func (s *AuthService) ChangePassword(ctx context.Context, userID int, oldPassword, newPassword string) error {
	user, err := s.userRepo.FindByID(ctx, userID)
	if err != nil {
		return err
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.HashedPassword), []byte(oldPassword)); err != nil {
		return ErrInvalidCredentials
	}

	hashed, err := bcrypt.GenerateFromPassword([]byte(newPassword), bcrypt.DefaultCost)
	if err != nil {
		return err
	}

	return s.userRepo.UpdatePassword(ctx, userID, string(hashed))
}

func (s *AuthService) GetCurrentUser(ctx context.Context, userID int) (*models.User, error) {
	user, err := s.userRepo.FindByID(ctx, userID)
	if err != nil {
		return nil, err
	}
	return user, nil
}
